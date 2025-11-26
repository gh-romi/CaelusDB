"""
URL configuration for CaelusDB_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""



from django.contrib import admin
from django.urls import path
# 1. Importujeme vestavěné pohledy pro autentizaci
from django.contrib.auth import views as auth_views
from main import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.verejny_seznam_letu, name='home'),

    # 2. Přidáme cestu pro přihlášení
    # Říkáme: "Použij vestavěný LoginView, ale vzhled si vezmi z naší šablony main/login.html"
    path('login/', auth_views.LoginView.as_view(template_name='main/login.html'), name='login'),

    # 3. Přidáme cestu pro odhlášení
    # next_page='/' znamená, že po odhlášení se vrátí na úvodní stránku
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # (URL pro rezervaci už tu máte)
    path('rezervace/<str:flight_ids>/', views.rezervace_detail, name='rezervace_detail'),

    path('registrace/', views.registrace, name='registrace'),

    path('profil/', views.muj_profil, name='muj_profil'),

    # Vestavěná změna hesla (bezpečná)
    path('profil/zmena-hesla/', auth_views.PasswordChangeView.as_view(
        template_name='main/zmena_hesla.html',
        success_url='/profil/'
    ), name='zmena_hesla'),

    path('platba/<int:rezervace_id>/', views.platba, name='platba'),

    path('platba/potvrzeni/<int:rezervace_id>/', views.potvrzeni_platby, name='potvrzeni_platby'),

    path('moje-rezervace/', views.moje_rezervace, name='moje_rezervace'),

    path('moje-rezervace/<int:rezervace_id>/', views.detail_moje_rezervace, name='detail_moje_rezervace'),

    path('rezervace/smazat/<int:rezervace_id>/', views.smazat_rezervaci, name='smazat_rezervaci'),
    path('letenka/upravit/<int:letenka_id>/', views.upravit_letenku, name='upravit_letenku'),

    path('letenka/presadit/<int:letenka_id>/', views.zmenit_sedadlo, name='zmenit_sedadlo'),

    path('moje-lety/', views.moje_lety, name='moje_lety'),
    path('moje-lety/<int:let_id>/', views.detail_moje_lety, name='detail_moje_lety'),

    # --- SPRÁVA LETŮ (MANAGEMENT) ---
    path('management/lety/novy/', views.management_novy_let, name='management_novy_let'),

    # --- API ENDPOINTY ---
    path('api/load-airline-data/', views.api_load_airline_data, name='api_load_airline_data'),
    path('api/load-flight-detail/', views.api_load_flight_detail, name='api_load_flight_detail'),
    path('api/check-collisions/', views.api_check_collisions, name='api_check_collisions'),
    path('api/delete-flight/', views.api_delete_flight, name='api_delete_flight'),  # NOVÉ
]
