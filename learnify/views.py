from django.shortcuts import redirect, render, HttpResponse, get_object_or_404
from coder.models import *
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from time import time

# ✅ FIX: correct settings import
from django.conf import settings

import razorpay

# ✅ Razorpay client (FIXED)
client = razorpay.Client(auth=(settings.KEY_ID, settings.KEY_SECRET))


# ---------------- HOME ----------------
def BASE(request):
    return render(request, 'base.html')


def Home(request):
    category = Categories.objects.all().order_by('id')[0:8]
    course = Course.objects.filter(status='PUBLISH').order_by('id')

    return render(request, 'index.html', {
        'category': category,
        'course': course,
    })


# ---------------- ABOUT ----------------
def About(request):
    category = Categories.get_all_category(Categories)
    return render(request, 'main/about.html', {'category': category})


# ---------------- CONTACT ----------------
def Contact_us(request):
    if request.method == "POST":
        Contact.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            subject=request.POST.get('subject'),
            message=request.POST.get('message')
        )
        messages.success(request, 'Thanks for Contact us !')
        return redirect('contact')

    return render(request, 'main/contact.html')


# ---------------- COURSES ----------------
def courses(request):
    return render(request, 'main/courses.html', {
        'category': Categories.get_all_category(Categories),
        'level': Level.objects.all(),
        'course': Course.objects.all(),
        'Free_Course_count': Course.objects.filter(price=0).count(),
        'Paid_Course_count': Course.objects.filter(price__gte=1).count(),
    })


# ---------------- COURSE DETAILS ----------------
@login_required(login_url='login')
def course_details(request, slug):
    course = get_object_or_404(Course, slug=slug)

    time_duration = Video.objects.filter(course=course).aggregate(
        sum=Sum('time_duration')
    )

    comments = Comment.objects.filter(course=course)

    try:
        check_enroll = UserCourse.objects.get(user=request.user, course=course)
    except UserCourse.DoesNotExist:
        check_enroll = None

    return render(request, 'course/course_details.html', {
        'course': course,
        'time_duration': time_duration,
        'comments': comments,
        'check_enroll': check_enroll,
        'category': Categories.get_all_category(Categories),
    })


# ---------------- CHECKOUT + RAZORPAY ----------------
@login_required(login_url='login')
def checkout(request, slug):
    course = get_object_or_404(Course, slug=slug)
    order = None

    # FREE COURSE
    if course.price == 0:
        UserCourse.objects.create(user=request.user, course=course)
        messages.success(request, "Course enrolled successfully!")
        return redirect('my-course')

    # PAYMENT CREATE
    action = request.GET.get('action')

    if action == "create_payment" and request.method == "POST":

        amount = int(course.price * 100)

        order_data = client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": f"learnify_{int(time())}"
        })

        Payment.objects.create(
            user=request.user,
            course=course,
            order_id=order_data['id']
        )

        order = order_data

    return render(request, 'checkout/checkout.html', {
        'course': course,
        'order': order,
    })


# ---------------- VERIFY PAYMENT ----------------
@csrf_exempt
def verify_payment(request):
    if request.method == "POST":
        data = request.POST

        try:
            client.utility.verify_payment_signature(data)

            payment = Payment.objects.get(order_id=data['razorpay_order_id'])
            payment.payment_id = data['razorpay_payment_id']
            payment.status = True
            payment.save()

            usercourse = UserCourse.objects.create(
                user=payment.user,
                course=payment.course
            )

            payment.user_course = usercourse
            payment.save()

            return render(request, 'verify_payment/success.html', {
                'payment': payment,
                'data': data,
            })

        except Exception as e:
            print("Payment Error:", e)
            return render(request, 'verify_payment/fail.html')

    return HttpResponse("Invalid Request")


# ---------------- MY COURSE ----------------
@login_required(login_url='login')
def my_course(request):
    return render(request, 'course/my_course.html', {
        'course': UserCourse.objects.filter(user=request.user),
        'category': Categories.get_all_category(Categories),
    })