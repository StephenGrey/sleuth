"""myproject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth import urls
from django.http import HttpResponseRedirect

urlpatterns = [
    url(r'^$', lambda r: HttpResponseRedirect('ownsearch/')),
    #url(r'^$',ownsearch.views.do_search),
    url(r'^admin/', admin.site.urls),
    url(r'^ownsearch/',include('ownsearch.urls')),
    url(r'^documents/',include('documents.urls')),
    url(r'^scraper/',include('scraper.urls')),
    url(r'^whatsapp/',include('whatsapp.urls')),
    url(r'^tests/',include('tests.urls')),
    url(r'^accounts/login/$', auth_views.LoginView.as_view(),name='login'),
    url(r'^accounts/logout/$', auth_views.LogoutView, name='logout'),
    url(r'^accounts/password_reset/$', auth_views.PasswordResetView, name='password_reset'),
    url(r'^accounts/password/reset/confirm/$', 
             auth_views.PasswordResetConfirmView, name='password_reset_confirm'),
    url(r'^accounts/password/reset/complete/$', 
             auth_views.PasswordResetCompleteView, name='password_reset_done'),
]
