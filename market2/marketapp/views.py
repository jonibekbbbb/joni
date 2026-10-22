from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import CheckoutForm, ProfileForm, RegisterForm
from .models import Category, Order, OrderItem, Product, Profile


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def home(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    return render(
        request,
        'shop/home.html',
        {
            'categories': Category.objects.filter(parent__isnull=True),
            'new_products': products[:8],
            'sale_products': products.filter(discount_price__isnull=False)[:8],
        },
    )


def product_list(request, category_slug=None):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    category = None

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(
            Q(category=category) | Q(category__parent=category)
        )

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    min_price = request.GET.get('min', '').strip()
    max_price = request.GET.get('max', '').strip()
    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except InvalidOperation:
            min_price = ''
    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except InvalidOperation:
            max_price = ''

    sort_map = {
        'cheap': 'price',
        'expensive': '-price',
        'new': '-created_at',
    }
    sort = request.GET.get('sort', '')
    products = products.order_by(sort_map.get(sort, '-created_at'))
    page = Paginator(products, 12).get_page(request.GET.get('page'))

    return render(
        request,
        'shop/product_list.html',
        {
            'page_obj': page,
            'category': category,
            'categories': Category.objects.all(),
            'query': query,
            'min_price': min_price,
            'max_price': max_price,
            'sort': sort,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.filter(is_active=True).prefetch_related('images'),
        slug=slug,
    )
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(id=product.id)
        .prefetch_related('images')[:4]
    )
    return render(
        request,
        'shop/product_detail.html',
        {'product': product, 'related': related},
    )


def cart_detail(request):
    cart = Cart(request)
    return render(
        request,
        'shop/cart.html',
        {'cart': cart, 'total': cart.total_price()},
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('shop:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Ro’yxatdan o’tdingiz. Xush kelibsiz!')
        return redirect('shop:home')

    return render(request, 'shop/register.html', {'form': form})


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile_obj)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Ma'lumotlar saqlandi")
        return redirect('shop:profile')

    orders = request.user.orders.prefetch_related('items')
    return render(
        request,
        'shop/profile.html',
        {'form': form, 'orders': orders},
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})


@login_required
def payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user, is_paid=False)
    # TODO: Click / Payme integration can be added here.
    return render(request, 'shop/payment.html', {'order': order})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    if product.stock == 0:
        return JsonResponse(
            {'ok': False, 'error': 'Mahsulot tugagan'},
            status=400,
        )

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        return JsonResponse(
            {'ok': False, 'error': 'Miqdor noto‘g‘ri'},
            status=400,
        )
    if quantity < 1:
        return JsonResponse(
            {'ok': False, 'error': 'Miqdor kamida 1 bo‘lishi kerak'},
            status=400,
        )

    cart = Cart(request)
    cart.add(product, quantity, request.POST.get('override') == '1')
    if _is_ajax(request):
        return JsonResponse(
            {
                'ok': True,
                'count': len(cart),
                'total': str(cart.total_price()),
            }
        )
    messages.success(request, f"{product.name} savatga qo'shildi")
    return redirect('shop:cart_detail')


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)
    if _is_ajax(request):
        return JsonResponse(
            {
                'ok': True,
                'count': len(cart),
                'total': str(cart.total_price()),
            }
        )
    return redirect('shop:cart_detail')


def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, "Savat bo'sh")
        return redirect('shop:home')

    initial = {}
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()
        if profile:
            initial = {
                'full_name': request.user.get_full_name(),
                'phone': profile.phone,
                'address': profile.address,
            }

    form = CheckoutForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                order = form.save(commit=False)
                order.user = request.user if request.user.is_authenticated else None
                order.total_price = Decimal('0')
                order.save()

                total = Decimal('0')
                for item in cart:
                    product = Product.objects.select_for_update().get(id=item['product'].id)
                    if product.stock < item['quantity']:
                        raise ValueError(f"{product.name} mahsulotining yetarli zaxirasi yo'q.")

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        price=item['price'],
                        quantity=item['quantity'],
                    )
                    product.stock -= item['quantity']
                    product.save(update_fields=['stock'])
                    total += item['total']

                order.total_price = total
                order.save(update_fields=['total_price'])
                cart.clear()
                messages.success(request, f"Buyurtma #{order.id} qabul qilindi.")
                return redirect('shop:home')
        except ValueError as exc:
            messages.error(request, str(exc))

    return render(
        request,
        'shop/checkout.html',
        {'cart': cart, 'total': cart.total_price(), 'form': form},
    )
