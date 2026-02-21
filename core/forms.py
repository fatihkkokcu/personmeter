from pathlib import Path

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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
    MAX_IMAGE_SIZE_MB = settings.PERSONMETER_MAX_IMAGE_UPLOAD_MB
    MAX_IMAGE_BYTES = settings.PERSONMETER_MAX_IMAGE_UPLOAD_BYTES
    MAX_IMAGE_PIXELS = settings.PERSONMETER_MAX_IMAGE_PIXELS
    ALLOWED_IMAGE_TYPES = {
        mime.lower() for mime in settings.PERSONMETER_ALLOWED_IMAGE_MIME_TYPES
    }
    ALLOWED_IMAGE_EXTENSIONS = {
        extension.lower() for extension in settings.PERSONMETER_ALLOWED_IMAGE_EXTENSIONS
    }
    ALLOWED_IMAGE_FORMATS = {
        image_format.upper() for image_format in settings.PERSONMETER_ALLOWED_IMAGE_FORMATS
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

        extension = Path(getattr(image, "name", "")).suffix.lower()
        if extension not in self.ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(
                "Unsupported image extension. Allowed: JPG, JPEG, PNG, WEBP, GIF."
            )

        content_type = (getattr(image, "content_type", "") or "").lower()
        if content_type and content_type not in self.ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                "Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF."
            )

        try:
            parsed_image = Image.open(image)
            image_format = (parsed_image.format or "").upper()
            width, height = parsed_image.size
            parsed_image.verify()
            if image_format not in self.ALLOWED_IMAGE_FORMATS:
                raise ValidationError(
                    "Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF."
                )
            if width * height > self.MAX_IMAGE_PIXELS:
                raise ValidationError(
                    "Image resolution is too large. Please upload a smaller image."
                )
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise ValidationError("Uploaded file is not a valid image.")
        finally:
            if hasattr(image, "seek"):
                try:
                    image.seek(0)
                except (OSError, ValueError):
                    pass

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
