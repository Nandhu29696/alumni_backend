import os
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from PIL import Image, UnidentifiedImageError


class EventBannerUploadMiddleware:
    allowed_types = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
    max_size = 5 * 1024 * 1024

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        upload_paths = {
            '/api/admin/events/upload-banner/': ('banner_image', 'event-banners'),
            '/api/auth/profile/images/': ('profile_images', 'profile-images'),
        }
        if request.path in upload_paths and request.method == 'POST':
            if request.path.endswith('upload-banner/'):
                fields = {'banner_image': request.FILES.get('banner_image')}
            else:
                fields = {name: request.FILES.get(name) for name in ('avatar_image', 'cover_image') if request.FILES.get(name)}
                if not fields:
                    return JsonResponse({'detail': 'avatar_image or cover_image file is required.'}, status=400)
            urls = {}
            for field, uploaded in fields.items():
                if not uploaded:
                    return JsonResponse({'detail': f'{field} file is required.'}, status=400)
                if uploaded.content_type not in self.allowed_types:
                    return JsonResponse({'detail': 'Only JPEG, PNG, and WebP images are supported.'}, status=400)
                if uploaded.size > self.max_size:
                    return JsonResponse({'detail': 'Images must be 5 MB or smaller.'}, status=400)
                try:
                    image = Image.open(uploaded)
                    image.verify()
                    uploaded.seek(0)
                except (UnidentifiedImageError, OSError):
                    return JsonResponse({'detail': 'The uploaded file is not a valid image.'}, status=400)
                extension = self.allowed_types[uploaded.content_type]
                filename = f'{uuid.uuid4().hex}{extension}'
                directory = Path(settings.MEDIA_ROOT) / upload_paths[request.path][1]
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory / filename
                with destination.open('wb+') as target:
                    for chunk in uploaded.chunks():
                        target.write(chunk)
                urls[field] = request.build_absolute_uri(f'{settings.MEDIA_URL}{upload_paths[request.path][1]}/{filename}')
            if request.path.endswith('upload-banner/'):
                request.uploaded_banner_url = urls['banner_image']
            else:
                request.uploaded_profile_urls = urls
        return self.get_response(request)
