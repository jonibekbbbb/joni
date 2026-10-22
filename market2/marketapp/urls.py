from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='shop/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('payment/<int:order_id>/', views.payment, name='payment'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('checkout/', views.checkout, name='checkout'),
    path(
        'cart/add/<int:product_id>/',
        views.cart_add,
        name='cart_add',
    ),
    path(
        'cart/remove/<int:product_id>/',
        views.cart_remove,
        name='cart_remove',
    ),
    path('products/', views.product_list, name='product_list'),
    path(
        'category/<slug:category_slug>/',
        views.product_list,
        name='category_products',
    ),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)





