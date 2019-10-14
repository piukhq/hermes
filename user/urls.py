from django.urls import path
from user import views

urlpatterns = [
    path("authenticate/", views.Authenticate.as_view(), name="authenticate_user"),
    path("auth/facebook/", views.FaceBookLogin.as_view(), name="authenticate_facebook_user"),
    path("auth/twitter/", views.TwitterLogin.as_view(), name="authenticate_twitter_user"),
    path("auth/verify_token/", views.VerifyToken.as_view(), name="verify_token"),
    path("v2_register/", views.NewRegister.as_view(), name="new_register_user"),
    path("register/", views.NewRegister.as_view(), name="register_user"),
    path("v2_login/", views.NewLogin.as_view(), name="new_login"),
    path("login/", views.NewLogin.as_view(), name="login"),
    path("me/", views.Users.as_view(), name="user_detail"),
    path("me/password/", views.ResetPassword.as_view(), name="reset_password"),
    path("me/settings/", views.UserSettings.as_view(), name="user_settings"),
    path("me/logout/", views.Logout.as_view(), name="logout"),
    path("forgotten_password/", views.ForgotPassword.as_view(), name="forgot_password"),
    path("reset_password/", views.ResetPasswordFromToken.as_view(), name="reset_password_from_token"),
    path("promo_code/", views.ApplyPromoCode.as_view(), name="promo_code"),
    path("validate_reset_token/", views.ValidateResetToken.as_view(), name="validate_reset"),
    path("settings/", views.Settings.as_view(), name="settings"),
    path("app_kit/", views.IdentifyApplicationKit.as_view(), name="app_kit"),
    path("renew_token/", views.Renew.as_view(), name="renew"),
    path(
        "organisation/terms_and_conditions/",
        views.OrganisationTermsAndConditions.as_view(),
        name="terms_and_conditions",
    ),
]
