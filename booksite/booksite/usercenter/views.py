# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, redirect
from django.http import Http404, HttpResponseBadRequest
from django import forms
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import login as auth_loginview
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from captcha.fields import CaptchaField

from booksite.book.models import BookPage
from booksite.usercenter.models import BookMark, User
from booksite.ajax import ajax_success, ajax_error


class MyAuthenticationForm(AuthenticationForm):
    captcha = CaptchaField()


class MyUserCreationForm(UserCreationForm):
    error_messages = {
        'duplicate_username': _("A user with that username already exists."),
        'password_mismatch': _("The two password fields didn't match."),
    }
    captcha = CaptchaField()
    username = forms.RegexField(label=_("Username"), max_length=30,
        regex=r'^[\w.@+-]+$',
        help_text=_("Required. 30 characters or fewer. Letters, digits and "
                      "@/./+/-/_ only."),
        error_messages={
            'invalid': _("This value may contain only letters, numbers and "
                         "@/./+/-/_ characters.")})
    email = forms.EmailField(label=_("Email"))
    password1 = forms.CharField(label=_("Password"),
        widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"),
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."))

    class Meta:
        model = User
        fields = ("username","email")

    def clean_username(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        username = self.cleaned_data["username"]
        try:
            User._default_manager.get(username=username)
        except User.DoesNotExist:
            return username
        raise forms.ValidationError(
            self.error_messages['duplicate_username'],
            code='duplicate_username',
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )
        return password2

    def save(self, commit=True):
        user = super(MyUserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


def login_view(request):
    return auth_loginview(
        request,
        template_name="usercenter/login.html",
        authentication_form=MyAuthenticationForm
    )


def signup(request):
    if request.method == "GET":
        return render(request,"usercenter/signup.html",{'form':MyUserCreationForm()})
    if request.method == "POST":
        signup_form = MyUserCreationForm(data=request.POST)
        if signup_form.is_valid():
            signup_form.save()
            user = authenticate(
                username=request.POST['username'],
                password=request.POST['password1'])
            auth_login(request, user)
            return redirect("/")
        else:
            return render(request,"usercenter/signup.html",{'form':signup_form})
    return HttpResponseBadRequest()


def logout_view(request):
    auth_logout(request)
    return redirect("/")


@login_required
def bookmark(request):
    C = {}
    C['bookmarks'] = BookMark.objects.filter(user=request.user)
    return render(request, "usercenter/bookmark.html", C)


@login_required
def add_bookmark(request):
    if request.method == 'POST':
        try:
            page = BookPage.objects.get(pk=request.POST.get('pageid','-1'))
        except:
            return ajax_error("章节错误!")
        obj, created = BookMark.objects.get_or_create(
            user=request.user,
            book=page.book,
            defaults={"page": page}
        )
        if not created:
            obj.delete()
            obj = BookMark.objects.create(
                user=request.user,
                book=page.book,
                page=page
            )
        else:
            page.book.get_bookrank().add_fav()
        return ajax_success(data="添加成功!")
    else:
        raise Http404


@login_required
def del_bookmark(request, bookmark_id):
    if request.method == 'POST':
        try:
            bookmark = BookMark.objects.get(pk=bookmark_id, user=request.user)
            book = bookmark.book
            bookmark.delete()
            book.get_bookrank().sub_fav()
        except:
            return ajax_error("无法删除此书签!")
        return ajax_success(data="删除成功!")
    else:
        raise Http404
