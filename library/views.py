from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q, Sum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import stripe
from .models import Book, Member, Loan, Fine, Author

stripe.api_key = settings.STRIPE_SECRET_KEY

# Helper function to check if user is staff (Librarian)
def is_librarian(user):
    """
    Checks if the user is a staff member (Librarian).

    This helper function is primarily used by the @user_passes_test decorator
    to restrict access to certain views that should only be accessible to librarians.

    Args:
        user (User): The Django User object to check.

    Returns:
        bool: True if the user is a staff member, False otherwise.
    """
    return user.is_staff

# --- Main UI ---
# This view renders the main menu [cite: 200]
@login_required
def main_menu(request):
    """
    Renders the main dashboard based on the user's role.

    If the user is a librarian (staff), it displays the 'Command Center' with library statistics,
    alerts for due loans, recent activity, and debt management.
    If the user is a regular member, it displays a personal dashboard with their active loans
    and outstanding fines.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'main_menu.html' template with the appropriate context.
    """
    today = timezone.now().date()
    
    if request.user.is_staff:
        # --- LIBRARIAN VIEW: Command Center ---
        total_books = Book.objects.count()
        books_checked_out = Book.objects.filter(status='Checked Out').count()
        books_available = total_books - books_checked_out
        
        total_members = Member.objects.count()
        
        # Financials
        total_outstanding_fines = Fine.objects.filter(status='Unpaid').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Alerts
        loans_due_today = Loan.objects.filter(duedate=today, returndate__isnull=True).count()
        
        # Recent Activity (Last 5 loans)
        recent_activity = Loan.objects.select_related('book', 'member').order_by('-checkoutdate', '-loanid')[:5]

        # NEW: Top Debtors (Members with highest unpaid fines)
        debtors = Fine.objects.filter(status='Unpaid').values(
            'member__memberid', 
            'member__firstname', 
            'member__lastname'
        ).annotate(
            total_debt=Sum('amount')
        ).order_by('-total_debt')[:5]

        context = {
            'is_librarian': True,
            'total_books': total_books,
            'books_checked_out': books_checked_out,
            'books_available': books_available,
            'total_members': total_members,
            'loans_due_today': loans_due_today,
            'total_outstanding_fines': total_outstanding_fines,
            'recent_activity': recent_activity,
            'debtors': debtors,
        }
    else:
        # --- MEMBER VIEW: Personal Dashboard ---
        context = {'is_librarian': False, 'today': today}
        try:
            # Find the member profile linked to this user's email
            member = Member.objects.get(email=request.user.email)
            
            # Get their active loans
            my_loans = Loan.objects.filter(member=member, returndate__isnull=True).select_related('book')
            
            # Get their unpaid fines
            my_fines = Fine.objects.filter(member=member, status='Unpaid')
            total_fine_amount = sum(fine.amount for fine in my_fines)
            
            context.update({
                'member': member,
                'my_loans': my_loans,
                'my_fines_count': my_fines.count(),
                'total_fine_amount': total_fine_amount,
            })
        except Member.DoesNotExist:
            # Fallback if their email doesn't match a member record
            messages.warning(request, "We couldn't find a library card linked to your email.")
            
    # It renders the 'main_menu.html' template with the context.
    return render(request, 'library/main_menu.html', context)

# --- Scenario 1: New Member Registration ---
# This view renders the "Register Member" page
@user_passes_test(is_librarian)
def register_member_view(request):
    """
    Registers a new library member.

    This view handles the form submission for creating a new Member record.
    It expects 'fname', 'lname', 'email', and 'phone' in the POST data.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'register_member.html' template or a redirect on success.
    """
    if request.method == 'POST':
        first_name = request.POST.get('fname')
        last_name = request.POST.get('lname')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        
        try:
            Member.objects.create(
                firstname=first_name,
                lastname=last_name,
                email=email,
                phonenumber=phone,
                membershipstatus='Active'
            )
            messages.success(request, 'Member registered successfully!')
            return redirect('register_member')
        except Exception as e:
            messages.error(request, f'Error registering member: {e}')

    return render(request, 'library/register_member.html')

# --- Scenario 2: Add New Book ---
@user_passes_test(is_librarian)
def add_book_view(request):
    """
    Adds a new book to the library inventory.

    This view handles the form submission for adding a new Book.
    It gets or creates the Author and then creates the Book record.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'add_book.html' template or a redirect on success.
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        author_name = request.POST.get('author_name')
        isbn = request.POST.get('isbn')
        genre = request.POST.get('genre')
        
        try:
            # Get or Create Author
            author, created = Author.objects.get_or_create(authorname=author_name)
            
            # Create Book
            Book.objects.create(
                title=title,
                author=author,
                isbn=isbn,
                genre=genre,
                status='Available'
            )
            messages.success(request, 'Book added successfully!')
            return redirect('add_book')
        except Exception as e:
            messages.error(request, f'Error adding book: {e}')

    # Fetch all authors for the datalist
    authors = Author.objects.all().order_by('authorname')
    return render(request, 'library/add_book.html', {'authors': authors})

# --- Scenario 3: Member Lookup & History ---
@user_passes_test(is_librarian)
def member_list_view(request):
    """
    Lists all members with search functionality.

    Allows librarians to search for members by name, email, or ID.
    If no search query is provided, it lists the first 50 members.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'member_list.html' template with the list of members.
    """
    query = request.GET.get('q', '')
    members = []
    
    if query:
        # Search by name, email, or ID
        members = Member.objects.filter(
            Q(firstname__icontains=query) | 
            Q(lastname__icontains=query) | 
            Q(email__icontains=query) |
            Q(memberid__icontains=query)
        )
    else:
        # Show all members (limit to 50 for performance)
        members = Member.objects.all()[:50]
        
    return render(request, 'library/member_list.html', {'members': members, 'query': query})

@user_passes_test(is_librarian)
def member_detail_view(request, member_id):
    """
    Displays detailed history for a specific member.

    Shows the member's active loans, loan history, and fine history.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.
        member_id (int): The ID of the member to retrieve.

    Returns:
        HttpResponse: The rendered 'member_detail.html' template with member details.
    """
    try:
        member = Member.objects.get(memberid=member_id)
        
        # Active Loans (Not returned)
        active_loans = Loan.objects.filter(member=member, returndate__isnull=True).select_related('book')
        
        # Loan History (Returned)
        loan_history = Loan.objects.filter(member=member, returndate__isnull=False).select_related('book').order_by('-returndate')
        
        # Fines
        fines = Fine.objects.filter(member=member).select_related('loan__book').order_by('-fineid')
        
        context = {
            'member': member,
            'active_loans': active_loans,
            'loan_history': loan_history,
            'fines': fines,
            'today': timezone.now().date()
        }
        return render(request, 'library/member_detail.html', context)
        
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('member_list')

# --- Scenario 4: Manage Books ---
@user_passes_test(is_librarian)
def book_list_view(request):
    """
    Lists all books with search functionality.

    Allows librarians to search for books by title, author, or ISBN.
    If no search query is provided, it lists the first 50 books.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'book_list.html' template with the list of books.
    """
    query = request.GET.get('q', '')
    books = []
    
    if query:
        books = Book.objects.filter(
            Q(title__icontains=query) | 
            Q(author__authorname__icontains=query) | 
            Q(isbn__icontains=query)
        )
    else:
        # Limit to 50 for performance
        books = Book.objects.all().select_related('author')[:50]
        
    return render(request, 'library/book_list.html', {'books': books, 'query': query})

@user_passes_test(is_librarian)
def book_detail_view(request, book_id):
    """
    Displays and updates details for a specific book.

    Allows librarians to view book details and loan history.
    Also handles the form submission to update book information.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.
        book_id (int): The ID of the book to retrieve.

    Returns:
        HttpResponse: The rendered 'book_detail.html' template with book details.
    """
    try:
        book = Book.objects.select_related('author').get(bookid=book_id)
        
        if request.method == 'POST':
            title = request.POST.get('title')
            author_name = request.POST.get('author_name')
            isbn = request.POST.get('isbn')
            genre = request.POST.get('genre')
            status = request.POST.get('status')
            
            try:
                # Update Author (or create new if changed)
                author = Author.objects.filter(authorname__iexact=author_name).first()
                if not author:
                    author = Author.objects.create(authorname=author_name)
                
                book.title = title
                book.author = author
                book.isbn = isbn
                book.genre = genre
                book.status = status
                book.save()
                
                messages.success(request, 'Book details updated successfully!')
                return redirect('book_detail', book_id=book.bookid)
                
            except Exception as e:
                messages.error(request, f'Error updating book: {e}')

        # Loan History for this book
        loan_history = Loan.objects.filter(book=book).select_related('member').order_by('-checkoutdate')
        
        # Active Loan (Current Borrower)
        active_loan = Loan.objects.filter(book=book, returndate__isnull=True).select_related('member').first()
        
        authors = Author.objects.all().order_by('authorname') # For datalist
        
        context = {
            'book': book,
            'loan_history': loan_history,
            'active_loan': active_loan,
            'authors': authors
        }
        return render(request, 'library/book_detail.html', context)
        
    except Book.DoesNotExist:
        messages.error(request, 'Book not found.')
        return redirect('book_list')

# --- Scenario 5: Notify Debtor ---
@user_passes_test(is_librarian)
def notify_debtor_view(request, member_id):
    """
    Sends an email reminder to a member about outstanding fines.

    Calculates the total unpaid fines for the member and sends an HTML email
    reminder using the configured SMTP backend.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.
        member_id (int): The ID of the member to notify.

    Returns:
        HttpResponse: A redirect to the 'main_menu' view.
    """
    try:
        member = Member.objects.get(memberid=member_id)
        
        # Calculate total debt
        unpaid_fines = Fine.objects.filter(member=member, status='Unpaid')
        total_debt = sum(fine.amount for fine in unpaid_fines)
        
        if total_debt > 0:
            subject = 'Action Required: Outstanding Library Fines'
            account_url = request.build_absolute_uri('/fees/')
            
            # Plain text fallback
            text_body = (
                f"Dear {member.firstname},\n\n"
                f"This is a reminder that you have outstanding fines totaling ${total_debt}.\n"
                f"Please log in to your account to view details and make a payment: {account_url}\n\n"
                f"Thank you,\nBookworm Library"
            )

            # HTML Version
            html_body = f"""
            <html>
            <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; margin: 0; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <div style="background-color: #2c3e50; padding: 25px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Bookworm Library</h1>
                    </div>
                    <div style="padding: 40px 30px;">
                        <h2 style="color: #2c3e50; margin-top: 0; font-size: 20px;">Outstanding Balance Notice</h2>
                        <p>Dear {member.firstname},</p>
                        <p>We hope you are enjoying your reading journey with us.</p>
                        <p>This is a friendly reminder that your account currently has an outstanding balance for overdue items.</p>
                        
                        <div style="background-color: #fff5f5; border-left: 4px solid #e74c3c; padding: 15px; margin: 25px 0; border-radius: 4px;">
                            <p style="margin: 0; font-size: 1.1em; color: #c0392b;"><strong>Total Amount Due:</strong> <span style="font-size: 1.3em; font-weight: bold;">${total_debt}</span></p>
                        </div>

                        <p>Please log in to your library account to view the specific details of these fines and to process your payment securely.</p>
                        
                        <div style="text-align: center; margin-top: 35px; margin-bottom: 20px;">
                            <a href="{account_url}" style="background-color: #3498db; color: white; padding: 14px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px; display: inline-block; box-shadow: 0 4px 6px rgba(52, 152, 219, 0.2);">View My Account</a>
                        </div>
                    </div>
                    <div style="background-color: #f8fafc; padding: 20px; text-align: center; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0;">
                        <p style="margin: 5px 0;">&copy; {timezone.now().year} Bookworm Library System</p>
                        <p style="margin: 5px 0;">This is an automated message. Please do not reply directly to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Create the email object
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.DEFAULT_FROM_EMAIL
            msg['To'] = member.email
            msg['Subject'] = subject
            
            # Attach both parts (text first, then HTML)
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))

            # Send using smtplib
            server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
            server.starttls()
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            messages.success(request, f'Reminder email sent to {member.email}.')
        else:
            messages.info(request, 'This member has no outstanding fines.')
            
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
    except Exception as e:
        messages.error(request, f'Error sending email: {e}')
        
    return redirect('main_menu')

# --- Scenario 6: Book Check-Out ---
# This view renders the "Check-Out" page
@user_passes_test(is_librarian)
def checkout_view(request):
    """
    Processes a book checkout for a member.

    Creates a new Loan record if the book is available.
    Updates the book status to 'Checked Out'.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'checkout.html' template or a redirect on success.
    """
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        book_id = request.POST.get('book_id')
        
        try:
            member = Member.objects.get(memberid=member_id)
            book = Book.objects.get(bookid=book_id)
            
            if book.status != 'Available':
                 messages.error(request, 'Book is not available.')
            else:
                Loan.objects.create(
                    book=book,
                    member=member,
                    checkoutdate=timezone.now().date(),
                    duedate=timezone.now().date() + timedelta(days=14)
                )
                book.status = 'Checked Out'
                book.save()
                messages.success(request, 'Book checked out successfully!')
                return redirect('checkout')
        except Member.DoesNotExist:
            messages.error(request, 'Member not found.')
        except Book.DoesNotExist:
            messages.error(request, 'Book not found.')
        except Exception as e:
             messages.error(request, f'Error: {e}')

    return render(request, 'library/checkout.html')

# --- Scenario 7: Book Return ---
# This view renders the "Return" page
@user_passes_test(is_librarian)
def return_view(request):
    """
    Processes a book return and calculates fines if overdue.

    Updates the Loan record with the return date and sets the book status to 'Available'.
    If the book is returned after the due date, a Fine record is created.
    Only accessible by librarians.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'return.html' template or a redirect on success.
    """
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        
        try:
            book = Book.objects.get(bookid=book_id)
            # Find active loan
            loan = Loan.objects.filter(book=book, returndate__isnull=True).first()
            
            if loan:
                return_date = timezone.now().date()
                loan.returndate = return_date
                loan.save()
                
                book.status = 'Available'
                book.save()
                
                # Calculate Fine if returned late
                if return_date > loan.duedate:
                    overdue_delta = return_date - loan.duedate
                    overdue_days = overdue_delta.days
                    # Assuming $1.00 fine per day
                    fine_amount = Decimal(overdue_days) * Decimal('1.00')
                    
                    Fine.objects.create(
                        loan=loan,
                        member=loan.member,
                        amount=fine_amount,
                        status='Unpaid'
                    )
                    messages.warning(request, f'Book returned late ({overdue_days} days). Fine of ${fine_amount} has been applied.')
                else:
                    messages.success(request, 'Book returned successfully!')
                
                return redirect('return_book')
            else:
                messages.error(request, 'No active loan found for this book.')
                
        except Book.DoesNotExist:
            messages.error(request, 'Book not found.')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'library/return.html')

# --- Scenario 8: Catalog Search ---
# This view renders the "Search" page
@login_required
def search_view(request):
    """
    Searches the book catalog.

    Allows users to search for books by title or author.
    Accessible by both librarians and members.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'search.html' template with search results.
    """
    results = None
    if request.method == 'GET' and 'search_term' in request.GET:
        search_term = request.GET.get('search_term')
        search_type = request.GET.get('search_type')
        
        if search_term:
            if search_type == 'title':
                results = Book.objects.filter(title__icontains=search_term)
            elif search_type == 'author':
                results = Book.objects.filter(author__authorname__icontains=search_term)
            
    return render(request, 'library/search.html', {'results': results})

# --- Scenario 9: View/Assess Late Fees ---
# This view renders the "View Fees" page
@login_required
def fees_view(request):
    """
    Displays outstanding fines.

    Librarians can view fines for any member by providing a 'member_id' GET parameter.
    Members can only view their own fines.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: The rendered 'fees.html' template with the list of fines.
    """
    fines = None
    member = None
    
    # Logic for Librarians: Can search any member
    if request.user.is_staff:
        if request.method == 'GET' and 'member_id' in request.GET:
            member_id = request.GET.get('member_id')
            if member_id:
                try:
                    member = Member.objects.get(memberid=member_id)
                    fines = Fine.objects.filter(member=member, status='Unpaid')
                except Member.DoesNotExist:
                    messages.error(request, 'Member not found.')
    
    # Logic for Members: Can only see their own fines
    else:
        try:
            # Link Django User to Library Member via email
            member = Member.objects.get(email=request.user.email)
            fines = Fine.objects.filter(member=member, status='Unpaid')
        except Member.DoesNotExist:
            messages.error(request, 'No library membership found for your email address.')

    return render(request, 'library/fees.html', {'fines': fines, 'member': member})

# --- Scenario 10: Process Payment (Stripe) ---
@login_required
def create_checkout_session(request, fine_id):
    """
    Initiates a Stripe checkout session for paying a fine.

    Creates a Stripe Session and redirects the user to the Stripe payment page.
    Ensures that the user is authorized to pay the fine (either staff or the fine owner).

    Args:
        request (HttpRequest): The HTTP request object.
        fine_id (int): The ID of the fine to be paid.

    Returns:
        HttpResponse: A redirect to the Stripe checkout URL.
    """
    try:
        fine = Fine.objects.get(fineid=fine_id)
        
        # Security Check: Ensure user owns the fine
        if not request.user.is_staff:
             if fine.member.email != request.user.email:
                 messages.error(request, "You are not authorized to pay this fine.")
                 return redirect('view_fees')

        # Create a Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Library Fine - Book: {fine.loan.book.title}',
                    },
                    'unit_amount': int(fine.amount * 100), # Stripe uses cents
                },
                'quantity': 1,
            }],
            mode='payment',
            # Where to send the user after payment
            success_url=request.build_absolute_uri(f'/payment_success/{fine_id}/'),
            cancel_url=request.build_absolute_uri(f'/fees/?member_id={fine.member.memberid}'),
        )
        
        return redirect(session.url, code=303)
    except Fine.DoesNotExist:
        messages.error(request, 'Fine record not found.')
        return redirect('view_fees')
    except Exception as e:
        messages.error(request, f'Error creating checkout session: {e}')
        # Redirect back to fees page if possible, or main menu
        if 'fine' in locals():
             return redirect(f'/fees/?member_id={fine.member.memberid}')
        return redirect('view_fees')

@login_required
def payment_success(request, fine_id):
    """
    Handles successful payment callback from Stripe.

    Updates the fine status to 'Paid' after a successful transaction.
    Redirects the user back to the fees page.

    Args:
        request (HttpRequest): The HTTP request object.
        fine_id (int): The ID of the fine that was paid.

    Returns:
        HttpResponse: A redirect to the 'fees_view'.
    """
    try:
        fine = Fine.objects.get(fineid=fine_id)
        fine.status = 'Paid'
        fine.save()
        messages.success(request, f"Payment of ${fine.amount} successful via Stripe!")
        return redirect(f'/fees/?member_id={fine.member.memberid}')
    except Fine.DoesNotExist:
        messages.error(request, 'Fine record not found.')
        return redirect('view_fees')
