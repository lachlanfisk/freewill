from django.urls import path
from . import views

urlpatterns = [
   path("", views.home, name="home"),
   path('create_group/', views.create_group, name='create_group'),
   path('group/<int:group_id>/', views.group_detail, name='group_detail'),
   
   path('group/<int:group_id>/settings/', views.edit_group_settings, name='group_settings'),
   path('group/<int:group_id>/transfer_ownership/', views.transfer_ownership, name='transfer_ownership'),
   path('group/<int:group_id>/delete/', views.delete_group, name='delete_group'),
   path('group/<int:group_id>/leave/', views.leave_group, name='leave_group'),

   path('group/<int:group_id>/member/<int:user_id>/manage/', views.manage_member_action, name='manage_member_action'),

   path('group/<int:group_id>/join/', views.join_public_group, name='join_public_group'),

   path('group/<int:group_id>/invite/', views.invite_users, name='invite_users'),
   path('group/<int:group_id>/invite-response/', views.respond_to_invite, name='respond_to_invite'),

   path('group/<int:group_id>/request-to-join/', views.request_to_join_group, name='request_to_join_group'),
   path('group/<int:group_id>/request/<int:request_id>/<str:action>/', views.handle_join_request, name='handle_join_request'),
   path('delete-join-request/<int:request_id>/', views.delete_join_request, name='delete_join_request'),

   path('group/<int:group_id>/edit/<int:edit_comment_id>/', views.group_detail, name='edit_comment'),
   path('comment/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
   path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
]