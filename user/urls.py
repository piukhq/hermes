from django.conf.urls import patterns, url
from user.views import (Users, Register, Login, Authenticate, FaceBookLogin, TwitterLoginWeb,
                        FaceBookLoginWeb, TwitterLogin, ResetPassword, ValidatePromoCode)


urlpatterns = patterns('user',
                       url(r'authenticate/?$', Authenticate.as_view(), name='authenticate_user'),
                       url(r'auth/facebook/?$', FaceBookLogin.as_view(), name='authenticate_facebook_user'),
                       url(r'auth/facebook_web/?$', FaceBookLoginWeb.as_view(), name='auth_facebook_web'),
                       url(r'auth/twitter/?$', TwitterLogin.as_view(), name='authenticate_twitter_user'),
                       url(r'auth/twitter_web/?$', TwitterLoginWeb.as_view(), name='authenticate_twitter_user'),
                       url(r'register/?$', Register.as_view(), name='register_user'),
                       url(r'login/?$', Login.as_view(), name='login'),
                       url(r'me$', Users.as_view(), name='user_detail'),
                       url(r'me/password$', ResetPassword.as_view(), name='user_detail'),
                       url(r'promo_code', ValidatePromoCode.as_view(), name='user_detail'),
                       )
