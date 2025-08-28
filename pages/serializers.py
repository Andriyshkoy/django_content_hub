from typing import Any, Dict, Type

from rest_framework import serializers

from .models import AudioContent, Page, PageContent, VideoContent


class PageListSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="page-detail")

    class Meta:
        model = Page
        fields = ["id", "title", "url"]


class VideoContentSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = VideoContent
        fields = ["id", "type", "title", "counter", "file_url", "subtitles_url"]

    def get_type(self, obj) -> str:
        return "video"


class AudioContentSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()

    class Meta:
        model = AudioContent
        fields = ["id", "type", "title", "counter", "text"]

    def get_type(self, obj) -> str:
        return "audio"


CONTENT_SERIALIZER_MAP: Dict[Type, Type[serializers.ModelSerializer]] = {
    VideoContent: VideoContentSerializer,
    AudioContent: AudioContentSerializer,
}


class PageContentSerializer(serializers.Serializer):
    def to_representation(self, instance: PageContent) -> Dict[str, Any]:
        obj = instance.content_object
        serializer_class = CONTENT_SERIALIZER_MAP.get(type(obj))
        if serializer_class is None:
            raise ValueError(f"No serializer for type {type(obj)}")
        return serializer_class(obj, context=self.context).data


class PageDetailSerializer(serializers.ModelSerializer):
    contents = PageContentSerializer(many=True)

    class Meta:
        model = Page
        fields = ["id", "title", "contents"]
