# test_url_normalization.py - Integration tests for URL normalization

import pytest
import json
from django.test import Client
from core.models import Noticia, Voto
from django.contrib.auth.models import User


