from cryptography.fernet import Fernet, InvalidToken

from social_publishing_service.core.errors import SocialPublishingError


class TokenCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise SocialPublishingError(
                503, "ENCRYPTION_KEY_REQUIRED", "Social token encryption key is required"
            )
        self.fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise SocialPublishingError(
                503, "TOKEN_DECRYPTION_FAILED", "Stored social token cannot be decrypted"
            ) from exc
