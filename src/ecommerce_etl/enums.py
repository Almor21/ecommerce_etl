from __future__ import annotations

from enum import StrEnum


# Valid product categories, used by the accepted_values check.
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


# Valid order lifecycle statuses.
# "unknown" and blanks are deliberately absent here: they get normalized to null.
class OrderStatus(StrEnum):
    DELIVERED = "delivered"
    SHIPPED = "shipped"
    PROCESSING = "processing"
    CANCELED = "canceled"
    RETURNED = "returned"


# Valid payment types.
class PaymentType(StrEnum):
    CREDIT_CARD = "credit_card"
    BOLETO = "boleto"
    VOUCHER = "voucher"
    DEBIT_CARD = "debit_card"
    PIX = "pix"
