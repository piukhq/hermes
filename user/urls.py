from django.conf.urls import patterns, url
from user.views import (Users, Register, NewRegister, Login, NewLogin, Authenticate, FaceBookLogin, TwitterLoginWeb,
                        FaceBookLoginWeb, TwitterLogin, ResetPassword, ValidatePromoCode, ForgotPassword,
                        ValidateResetToken, ResetPasswordFromToken, Settings, UserSettings, IdentifyApplicationKit,
                        VerifyToken)


urlpatterns = patterns('user',
                       url(r'authenticate/?$', Authenticate.as_view(), name='authenticate_user'),
                       url(r'auth/facebook/?$', FaceBookLogin.as_view(), name='authenticate_facebook_user'),
                       url(r'auth/facebook_web/?$', FaceBookLoginWeb.as_view(), name='auth_facebook_web'),
                       url(r'auth/twitter/?$', TwitterLogin.as_view(), name='authenticate_twitter_user'),
                       url(r'auth/twitter_web/?$', TwitterLoginWeb.as_view(), name='authenticate_twitter_user'),
                       url(r'^auth/verify_token/?$', VerifyToken.as_view(), name='verify_token'),
                       url(r'^v2_register/?$', NewRegister.as_view(), name='new_register_user'),
                       url(r'^register/?$', Register.as_view(), name='register_user'),
                       url(r'^v2_login/?$', NewLogin.as_view(), name='new_login'),
                       url(r'^login/?$', Login.as_view(), name='login'),
                       url(r'me/?$', Users.as_view(), name='user_detail'),
                       url(r'me/password/?$', ResetPassword.as_view(), name='reset_password'),
                       url(r'me/settings/?$', UserSettings.as_view(), name='user_settings'),
                       url(r'forgotten_password/?$', ForgotPassword.as_view(), name='forgot_password'),
                       url(r'reset_password/?$', ResetPasswordFromToken.as_view(), name='reset_password_from_token'),
                       url(r'promo_code/?$', ValidatePromoCode.as_view(), name='promo_code'),
                       url(r'validate_reset_token/?$', ValidateResetToken.as_view(), name='validate_reset'),
                       url(r'settings/?$', Settings.as_view(), name='settings'),
                       url(r'^app_kit/?$', IdentifyApplicationKit.as_view(), name='app_kit'),
                       )
