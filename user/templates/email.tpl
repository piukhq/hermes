{% extends "mail_templated/base.tpl" %}

{% block subject %}
    Reset Bink password
{% endblock %}

{% block html %}
<center>
<img src='{{ hermes_url }}media/bink.jpg' alt='Bink'>
<h1 style='font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif; color: #F4136B;'>Forgotten Password</h1>
<hr style='height: 1px; color: #ccc; background-color: #ccc; border: none'>
<p style='font-family: "Lucida Sans Unicode", "Lucida Grande", sans-serif; color: #333;'>Click <a style='color: #F4136B; font-weight: bold' href='{{ link }}'>here</a> to choose your new Bink password.</p>
</center>
{% endblock %}