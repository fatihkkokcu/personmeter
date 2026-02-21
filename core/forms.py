from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from PIL import Image, UnidentifiedImageError

from .models import Category, Collection, CollectionItem, Person, Report

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user 

class AdvancedSearchForm(forms.Form):
    q = forms.CharField(
        label='Search',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search people...'})
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter tags (comma-separated)'
        })
    )
    min_rating = forms.DecimalField(
        min_value=0,
        max_value=10,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum rating'
        })
    )
    max_rating = forms.DecimalField(
        min_value=0,
        max_value=10,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Maximum rating'
        })
    )
    min_ratings_count = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum number of ratings'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()

class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['title', 'description', 'is_public']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class CollectionItemForm(forms.ModelForm):
    class Meta:
        model = CollectionItem
        fields = ['notes', 'order']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control'})
        }

class PersonForm(forms.ModelForm):
    MAX_IMAGE_SIZE_MB = 5
    MAX_IMAGE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
    ALLOWED_IMAGE_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }

    class Meta:
        model = Person
        fields = ['name', 'description', 'image', 'category', 'tags']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter tags (comma-separated)'})
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image

        if image.size > self.MAX_IMAGE_BYTES:
            raise ValidationError(
                f"Image size cannot exceed {self.MAX_IMAGE_SIZE_MB} MB."
            )

        content_type = (getattr(image, "content_type", "") or "").lower()
        if content_type and content_type not in self.ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                "Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF."
            )

        try:
            parsed_image = Image.open(image)
            parsed_image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError("Uploaded file is not a valid image.")
        finally:
            if hasattr(image, "seek"):
                image.seek(0)

        return image


class ReportForm(forms.Form):
    reason = forms.ChoiceField(
        choices=Report.REASON_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    details = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control form-control-sm",
                "rows": 2,
                "placeholder": "Optional details",
            }
        ),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput())
