from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Category, Collection, CollectionItem, Person

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
        queryset=Category.objects.all(),
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
    min_ratings_count = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum number of ratings'
        })
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('-created_at', 'Newest first'),
            ('created_at', 'Oldest first'),
            ('-avg_rating', 'Highest rated'),
            ('avg_rating', 'Lowest rated'),
            ('-rating_count', 'Most rated'),
            ('name', 'Name (A-Z)'),
            ('-name', 'Name (Z-A)'),
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    ) 

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