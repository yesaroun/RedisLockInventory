"""
커스텀 예외 정의

애플리케이션 전역에서 사용되는 커스텀 예외 클래스들입니다.
"""


class UserAlreadyExistsException(Exception):
    """
    중복된 사용자명으로 회원 가입을 시도할 때 발생하는 예외

    HTTP Status Code: 409 Conflict
    """

    def __init__(self, username: str):
        self.username = username
        self.message = f"User with username '{username}' already exists"
        super().__init__(self.message)


class InvalidCredentialsException(Exception):
    """
    인증 실패 시 발생하는 예외 (잘못된 비밀번호, 유효하지 않은 토큰 등)

    HTTP Status Code: 401 Unauthorized
    """

    def __init__(self, message: str = "Invalid credentials"):
        self.message = message
        super().__init__(self.message)


class UserNotFoundException(Exception):
    """
    사용자를 찾을 수 없을 때 발생하는 예외

    HTTP Status Code: 404 Not Found
    """

    def __init__(self, username: str):
        self.username = username
        self.message = f"User '{username}' not found"
        super().__init__(self.message)


class ProductNotFoundException(Exception):
    """
    상품을 찾을 수 없을 때 발생하는 예외

    HTTP Status Code: 404 Not Found
    """

    def __init__(self, product_id: int):
        self.product_id = product_id
        self.message = f"Product with id {product_id} not found"
        super().__init__(self.message)


class InsufficientStockException(Exception):
    """
    재고 부족 시 발생하는 예외

    HTTP Status Code: 400 Bad Request
    """

    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        self.message = (
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )
        super().__init__(self.message)


class LockAcquisitionException(Exception):
    """
    락 획득 실패 시 발생하는 예외

    HTTP Status Code: 409 Conflict
    """

    def __init__(self, resource: str, message: str = "Failed to acquire lock"):
        self.resource = resource
        self.message = f"{message} for resource: {resource}"
        super().__init__(self.message)


class ProductAlreadyExistsException(Exception):
    """
    중복된 상품명으로 상품을 생성하려 할 때 발생하는 예외

    HTTP Status Code: 409 Conflict
    """

    def __init__(self, name: str):
        self.name = name
        self.message = f"Product with name '{name}' already exists"
        super().__init__(self.message)
