from django import views as auth_views
#from Users.views import CustomPasswordResetView, CustomPasswordResetDoneView, CustomPasswordResetConfirmView, CustomPasswordResetCompleteView
from django.contrib import admin
from django.urls import path, include
from Users import views 
from Home import views as home_views
urlpatterns = [
    path('admin/', admin.site.urls),
   path('register/', views.register, name='register'),  # ✅ FIXED
    path('login/', views.Login, name='Login'),           # also fix consistency
]