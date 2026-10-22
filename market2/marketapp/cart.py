from decimal import Decimal

from .models import Product


CART_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(CART_KEY, {})

    def add(self, product, quantity=1, override=False):
        product_id = str(product.id)
        new_quantity = quantity if override else self.cart.get(product_id, 0) + quantity
        new_quantity = min(max(0, new_quantity), product.stock)

        if new_quantity:
            self.cart[product_id] = new_quantity
        else:
            self.cart.pop(product_id, None)
        self.save()

    def remove(self, product_id):
        self.cart.pop(str(product_id), None)
        self.save()

    def clear(self):
        self.session[CART_KEY] = {}
        self.cart = self.session[CART_KEY]
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(
            id__in=self.cart.keys(),
            is_active=True,
        )
        for product in products:
            quantity = self.cart[str(product.id)]
            price = product.final_price
            yield {
                'product': product,
                'quantity': quantity,
                'price': price,
                'total': price * quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    def total_price(self):
        return sum(
            (item['total'] for item in self),
            Decimal('0'),
        )
