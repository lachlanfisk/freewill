from django.urls import path
from . import views

urlpatterns = [
    path("", views.user, name="user"),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('send_confirmation_success_email', views.send_confirmation_success_email, name='send_confirmation_success_email'),
    path('send_login_email', views.send_login_email, name='send_login_email'),
    path('delete_account/', views.delete_account, name='delete_account'),
    path('confirm-delete/', views.confirm_delete_account, name='confirm_delete_account'),
]