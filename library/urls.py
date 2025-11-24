from django.urls import path
from . import views

urlpatterns = [
    # Main UI
    path('', views.main_menu, name='main_menu'),

    # Scenario UIs
    path('register/', views.register_member_view, name='register_member'),
    path('members/', views.member_list_view, name='member_list'),
    path('members/<int:member_id>/', views.member_detail_view, name='member_detail'),
    path('books/', views.book_list_view, name='book_list'),
    path('books/<int:book_id>/', views.book_detail_view, name='book_detail'),
    path('add_book/', views.add_book_view, name='add_book'),
    path('notify/<int:member_id>/', views.notify_debtor_view, name='notify_debtor'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('return/', views.return_view, name='return_book'),
    path('search/', views.search_view, name='search_catalog'),
    path('fees/', views.fees_view, name='view_fees'),
    
    # Payment
    path('pay_fine/<int:fine_id>/', views.create_checkout_session, name='pay_fine'),
    path('payment_success/<int:fine_id>/', views.payment_success, name='payment_success'),
]