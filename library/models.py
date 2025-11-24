from django.db import models

# Create your models here.

class Author(models.Model):
    authorid = models.AutoField(db_column='AuthorID', primary_key=True)
    authorname = models.CharField(db_column='AuthorName', max_length=255)
    biography = models.TextField(db_column='Biography', blank=True, null=True)
    birthyear = models.TextField(db_column='BirthYear', blank=True, null=True)
    nationality = models.CharField(db_column='Nationality', max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'authors'
    
    def __str__(self):
        return self.authorname

class Book(models.Model):
    bookid = models.AutoField(db_column='BookID', primary_key=True)
    title = models.CharField(db_column='Title', max_length=255)
    author = models.ForeignKey(Author, models.DO_NOTHING, db_column='AuthorID', blank=True, null=True)
    isbn = models.CharField(db_column='ISBN', unique=True, max_length=13)
    genre = models.CharField(db_column='Genre', max_length=100, blank=True, null=True)
    status = models.CharField(db_column='Status', max_length=50)

    class Meta:
        managed = False
        db_table = 'books'

    def __str__(self):
        return self.title

class Member(models.Model):
    memberid = models.AutoField(db_column='MemberID', primary_key=True)
    firstname = models.CharField(db_column='FirstName', max_length=100)
    lastname = models.CharField(db_column='LastName', max_length=100)
    email = models.CharField(db_column='Email', unique=True, max_length=255)
    phonenumber = models.CharField(db_column='PhoneNumber', max_length=20, blank=True, null=True)
    membershipstatus = models.CharField(db_column='MembershipStatus', max_length=50)

    class Meta:
        managed = False
        db_table = 'members'

    def __str__(self):
        return f"{self.firstname} {self.lastname}"

class Loan(models.Model):
    loanid = models.AutoField(db_column='LoanID', primary_key=True)
    book = models.ForeignKey(Book, models.DO_NOTHING, db_column='BookID', blank=True, null=True)
    member = models.ForeignKey(Member, models.DO_NOTHING, db_column='MemberID', blank=True, null=True)
    checkoutdate = models.DateField(db_column='CheckoutDate')
    duedate = models.DateField(db_column='DueDate')
    returndate = models.DateField(db_column='ReturnDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'loans'

    def __str__(self):
        return f"{self.book.title} borrowed by {self.member}"

class Fine(models.Model):
    fineid = models.AutoField(db_column='FineID', primary_key=True)
    loan = models.ForeignKey(Loan, models.DO_NOTHING, db_column='LoanID', blank=True, null=True)
    member = models.ForeignKey(Member, models.DO_NOTHING, db_column='MemberID', blank=True, null=True)
    amount = models.DecimalField(db_column='Amount', max_digits=5, decimal_places=2)
    status = models.CharField(db_column='Status', max_length=50)

    class Meta:
        managed = False
        db_table = 'fines'
