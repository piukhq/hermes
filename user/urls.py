from django.urls import re_path

from user import views

urlpatterns = [
    re_path(r"authenticate/?$", views.Authenticate.as_view(), name="authenticate_user"),
    re_path(r"auth/apple/?$", views.AppleLogin.as_view(), name="authenticate_apple_user"),
    re_path(r"^auth/verify_token/?$", views.VerifyToken.as_view(), name="verify_token"),
    re_path(r"^v2_register/?$", views.NewRegister.as_view(), name="new_register_user"),
    re_path(r"^register/?$", views.NewRegister.as_view(), name="register_user"),
    re_path(r"^v2_login/?$", views.NewLogin.as_view(), name="new_login"),
    re_path(r"^login/?$", views.NewLogin.as_view(), name="login"),
    re_path(r"me/?$", views.Users.as_view(), name="user_detail"),
    re_path(r"magic_links/?$", views.MakeMagicLink.as_view(), name="user_make_magic_link"),
    re_path(r"me/settings/?$", views.UserSettings.as_view(), name="user_settings"),
    re_path(r"me/logout/?$", views.Logout.as_view(), name="logout"),
    re_path(r"promo_code/?$", views.ApplyPromoCode.as_view(), name="promo_code"),
    re_path(r"settings/?$", views.Settings.as_view(), name="settings"),
    re_path(r"^app_kit/?$", views.IdentifyApplicationKit.as_view(), name="app_kit"),
    re_path(r"^renew_token/?$", views.Renew().as_view(), name="renew"),
    re_path(
        r"^organisation/terms_and_conditions/?$",
        views.OrganisationTermsAndConditions.as_view(),
        name="terms_and_conditions",
    ),
    re_path(r"^magic_links/access_tokens/?$", views.MagicLinkAuthView().as_view(), name="magic_link_auth"),
]
