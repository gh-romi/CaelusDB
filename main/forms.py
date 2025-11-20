from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm

UzivatelModel = get_user_model()


class CustomUserCreationForm(forms.ModelForm):
    """
    Formulář pro vytvoření uživatele POUZE s emailem a heslem.
    Dědíme z ModelForm, abychom obešli problémy s 'username'.
    """

    # Musíme ručně přidat pole pro heslo, která UserCreationForm dělal automaticky
    password = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Potvrzení hesla', widget=forms.PasswordInput)

    class Meta:
        model = UzivatelModel
        fields = ('email',)  # Jediné pole z modelu

    def clean_password2(self):
        # Validace, že se hesla shodují
        cd = self.cleaned_data
        if cd['password'] != cd['password2']:
            raise forms.ValidationError('Hesla se neshodují.')
        return cd['password2']  # Vrátíme potvrzené heslo

    def save(self, commit=True):
        # Nyní voláme našeho vlastního správce z models.py,
        # který ví, jak vytvořit uživatele bez 'username'.
        user = self.Meta.model.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        return user
# ------------------------------------


class CustomUserChangeForm(UserChangeForm):
    """
    Formulář pro úpravu uživatele.
    Tento formulář uvidíte po uložení.
    """
    class Meta:
        model = UzivatelModel
        # Zde jsou všechna ostatní pole
        fields = ('email', 'first_name', 'last_name', 'telefon', 'id_aerolinky', 'is_active', 'is_staff')


class PublicRegistrationForm(CustomUserCreationForm):
    """
    Formulář pro veřejnou registraci.
    Vynucuje jméno a příjmení.
    """
    first_name = forms.CharField(label="Křestní jméno", max_length=150, required=True)
    last_name = forms.CharField(label="Příjmení", max_length=150, required=True)

    class Meta(CustomUserCreationForm.Meta):
        # Dědíme model a pole z rodiče, ale přidáme jména
        fields = ('email', 'first_name', 'last_name')

    def save(self, commit=True):
        # 1. Uložíme základ (email + heslo) pomocí logiky rodiče
        user = super().save(commit=False)

        # 2. Ručně doplňujeme jména z formuláře do modelu
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        # 3. Uložíme do databáze
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    """
    Formulář pro úpravu vlastního profilu uživatele.
    """
    # Aerolinku zobrazíme, ale zakážeme editaci (disabled=True)
    # Musíme ji načíst ručně, protože v modelu je to ID, ale my chceme název
    airline_display = forms.CharField(
        label="Aerolinka",
        required=False,
        disabled=True,
        help_text="Aerolinku může změnit pouze administrátor."
    )

    class Meta:
        model = UzivatelModel
        fields = ('email', 'first_name', 'last_name', 'telefon', 'cislo_pasu')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pokud má uživatel aerolinku, vypíšeme její název do pole
        if self.instance.id_aerolinky:
            self.fields['airline_display'].initial = self.instance.id_aerolinky.nazev
