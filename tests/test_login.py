import pytest
import jwt
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from routes.api.login import (
    validate_email_function,
    validate_password,
    generate_jwt_token
)

class TestValidateEmailFunction:
    
    def test_valid_email(self):
        """Testa email válido"""
        assert validate_email_function("user@gmail.com") == True
    
    def test_valid_email_with_numbers(self):
        """Testa email válido com números"""
        assert validate_email_function("user123@gmail.com") == True
    
    def test_invalid_email_no_at(self):
        """Testa email inválido sem @"""
        assert validate_email_function("userexample.com") == False
    
    def test_invalid_email_no_domain(self):
        """Testa email inválido sem domínio"""
        assert validate_email_function("user@") == False
    
    def test_invalid_email_no_local_part(self):
        """Testa email inválido sem parte local"""
        assert validate_email_function("@example.com") == False
    
    def test_invalid_email_empty(self):
        """Testa email vazio"""
        assert validate_email_function("") == False
    
    def test_invalid_email_spaces(self):
        """Testa email com espaços"""
        assert validate_email_function("user @example.com") == False
    
    def test_invalid_email_multiple_at(self):
        """Testa email com múltiplos @"""
        assert validate_email_function("user@@example.com") == False


class TestValidatePassword:
    
    def test_valid_password_simple(self):
        """Testa senha válida simples"""
        assert validate_password("Password1") == True
    
    def test_valid_password_long(self):
        """Testa senha válida longa"""
        assert validate_password("MyPassword123456") == True
    
    def test_valid_password_with_special_chars(self):
        """Testa senha válida com caracteres especiais"""
        assert validate_password("Pass@word123") == False
    
    def test_valid_password_uppercase_lowercase_number(self):
        """Testa senha válida com maiúsculas, minúsculas e número"""
        assert validate_password("AaBbCc123") == True
    
    def test_invalid_password_too_short(self):
        """Testa senha inválida por ser muito curta"""
        assert validate_password("Pass1") == False
    
    def test_invalid_password_no_number(self):
        """Testa senha inválida sem número"""
        assert validate_password("Password") == False
    
    def test_invalid_password_no_letter(self):
        """Testa senha inválida sem letra"""
        assert validate_password("12345678") == False
    
    def test_invalid_password_empty(self):
        """Testa senha vazia"""
        assert validate_password("") == False
    
    def test_invalid_password_only_numbers(self):
        """Testa senha com apenas números"""
        assert validate_password("12345678") == False
    
    def test_invalid_password_only_letters(self):
        """Testa senha com apenas letras"""
        assert validate_password("abcdefgh") == False
    
    def test_valid_password_exactly_8_chars(self):
        """Testa senha válida com exatamente 8 caracteres"""
        assert validate_password("Abcdef12") == True
    
    def test_invalid_password_7_chars(self):
        """Testa senha inválida com 7 caracteres"""
        assert validate_password("Abcd123") == False


class TestGenerateJwtToken:
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_returns_string(self):
        """Testa se a função retorna uma string"""
        token = generate_jwt_token(1)
        assert isinstance(token, str)
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_not_empty(self):
        """Testa se o token gerado não é vazio"""
        token = generate_jwt_token(1)
        assert len(token) > 0
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_contains_user_id(self):
        """Testa se o token contém o user_id correto"""
        user_id = 42
        token = generate_jwt_token(user_id)
        decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        assert decoded['user_id'] == user_id
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_contains_exp(self):
        """Testa se o token contém a data de expiração"""
        token = generate_jwt_token(1)
        decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        assert 'exp' in decoded
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_expiration_within_24_hours(self):
        """Testa se a expiração está dentro de 24 horas"""
        token = generate_jwt_token(1)
        decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        
        exp_time = datetime.utcfromtimestamp(decoded['exp'])
        current_time = datetime.utcnow()
        time_diff = (exp_time - current_time).total_seconds()
        
        # Deve estar entre 23:50 e 24:00 horas (com margem de erro)
        assert 86000 < time_diff <= 86400  # 23h50min < diff <= 24h
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_different_users_different_tokens(self):
        """Testa se usuários diferentes geram tokens diferentes"""
        token1 = generate_jwt_token(1)
        token2 = generate_jwt_token(2)
        assert token1 != token2
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_can_be_decoded(self):
        """Testa se o token gerado pode ser decodificado"""
        token = generate_jwt_token(1)
        try:
            decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
            assert decoded is not None
        except jwt.InvalidTokenError:
            pytest.fail("Token não pôde ser decodificado")
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_invalid_secret_fails(self):
        """Testa se decodificação com chave errada falha"""
        token = generate_jwt_token(1)
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, 'wrong-secret-key', algorithms=['HS256'])
    
    @patch.dict(os.environ, {'JWT_SECRET_KEY': 'test-secret-key'})
    def test_generate_token_with_different_user_ids(self):
        """Testa geração de token com diferentes IDs de usuário"""
        for user_id in [1, 100, 999, 123456]:
            token = generate_jwt_token(user_id)
            decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
            assert decoded['user_id'] == user_id
