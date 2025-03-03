from django.http import JsonResponse

def health_check(request):
    """
    Simple health check endpoint for Docker healthcheck.
    Returns a 200 OK response to indicate the service is healthy.
    """
    return JsonResponse({"status": "healthy"})
