from django.urls import re_path
from user import views

urlpatterns = [
    re_path(r"authenticate/?$", views.Authenticate.as_view(), name="authenticate_user"),
    re_path(r"auth/facebook/?$", views.FaceBookLogin.as_view(), name="authenticate_facebook_user"),
    re_path(r"auth/twitter/?$", views.TwitterLogin.as_view(), name="authenticate_twitter_user"),
    re_path(r"^auth/verify_token/?$", views.VerifyToken.as_view(), name="verify_token"),
    re_path(r"^v2_register/?$", views.NewRegister.as_view(), name="new_register_user"),
    re_path(r"^register/?$", views.NewRegister.as_view(), name="register_user"),
    re_path(r"^v2_login/?$", views.NewLogin.as_view(), name="new_login"),
    re_path(r"^login/?$", views.NewLogin.as_view(), name="login"),
    re_path(r"me/?$", views.Users.as_view(), name="user_detail"),
    re_path(r"me/password/?$", views.ResetPassword.as_view(), name="reset_password"),
    re_path(r"me/settings/?$", views.UserSettings.as_view(), name="user_settings"),
    re_path(r"me/logout/?$", views.Logout.as_view(), name="logout"),
    re_path(r"forgotten_password/?$", views.ForgotPassword.as_view(), name="forgot_password"),
    re_path(r"reset_password/?$", views.ResetPasswordFromToken.as_view(), name="reset_password_from_token"),
    re_path(r"promo_code/?$", views.ApplyPromoCode.as_view(), name="promo_code"),
    re_path(r"validate_reset_token/?$", views.ValidateResetToken.as_view(), name="validate_reset"),
    re_path(r"settings/?$", views.Settings.as_view(), name="settings"),
    re_path(r"^app_kit/?$", views.IdentifyApplicationKit.as_view(), name="app_kit"),
    re_path(r"^renew_token/?$", views.Renew().as_view(), name="renew"),
    re_path(
        r"^organisation/terms_and_conditions/?$",
        views.OrganisationTermsAndConditions.as_view(),
        name="terms_and_conditions",
    ),
]
