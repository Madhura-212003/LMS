from django.urls import path
from lms.api import api
from lms.identity import browser_start,browser_callback

urlpatterns = [path('api/lms/auth/entra/start',browser_start),path('api/lms/auth/entra/callback',browser_callback),path('api/lms/', api.urls)]
