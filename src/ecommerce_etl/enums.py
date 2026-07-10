from __future__ import annotations

from enum import StrEnum


# Categorías válidas de products, usadas por el accepted_values check.
class ProductCategory(StrEnum):
    AUTOMOTIVE = "automotive"
    BEAUTY = "beauty"
    BOOKS = "books"
    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    FOOD = "food"
    FURNITURE = "furniture"
    GARDEN = "garden"
    HEALTH = "health"
    HOME_APPLIANCES = "home_appliances"
    MUSIC = "music"
    OFFICE_SUPPLIES = "office_supplies"
    PET_SHOP = "pet_shop"
    SPORTS = "sports"
    TOYS = "toys"


# Estados válidos del ciclo de vida de un pedido.
# "unknown" y los blancos NO están aquí a propósito: se normalizan a null.
class OrderStatus(StrEnum):
    DELIVERED = "delivered"
    SHIPPED = "shipped"
    PROCESSING = "processing"
    CANCELED = "canceled"
    RETURNED = "returned"


# Métodos de pago válidos
class PaymentType(StrEnum):
    CREDIT_CARD = "credit_card"
    BOLETO = "boleto"
    VOUCHER = "voucher"
    DEBIT_CARD = "debit_card"
    PIX = "pix"
