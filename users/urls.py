from django.urls import path
from . import views

urlpatterns = [
    # Home Page
    path("", views.user, name="user"),

    # Login/Register
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),

    # User/Profile Edit
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('email/confirm/<uidb64>/<token>/', views.confirm_email_change, name='confirm_email_change'),
    path('delete_account/', views.delete_account, name='delete_account'),
    path('confirm-delete/', views.confirm_delete_account, name='confirm_delete_account'),
    path('change-password/', views.change_password_view, name='change_password'),
]