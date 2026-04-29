
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index_view, name='index'),
    path('home', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('challenges/', views.challenges, name='challenges'),
    path('challenges/<int:pk>/', views.challenge_detail, name='challenge_detail'),
    path('shop/', views.shop, name='shop'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('seller/register/', views.seller_register, name='seller_register'),
    path('seller/login/', views.seller_login, name='seller_login'),
    path('seller/profile/', views.seller_profile, name='seller_profile'),
    path("api/accounts/", include("accounts.urls")),
    path("api/geography/", include("geography.urls")),
    path("learning/", include("learning.urls")),
    path("challenges-system/", include("challenges.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
