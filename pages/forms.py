from django import forms
from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteMixin
from django.contrib.contenttypes.models import ContentType

from .models import ContentBase, PageContent


def get_allowed_content_models():
    """Return a list of models allowed for ``PageContent.content_object``.

    Priority:
    - If ``settings.PAGES_ALLOWED_CONTENT_MODELS`` is defined (list of
      ``"app_label.ModelName"``), use it.
    - Otherwise, auto‑discover all non‑abstract subclasses of ``ContentBase``
      among installed apps (extensible: any subclass will be picked up
      automatically).
    """

    labels = getattr(settings, "PAGES_ALLOWED_CONTENT_MODELS", None)
    models_list = []
    if labels:
        for label in labels:
            try:
                app_label, model_name = label.split(".", 1)
                m = apps.get_model(app_label, model_name)
                if m is not None:
                    models_list.append(m)
            except Exception:
                # Ignore invalid labels silently to not break admin.
                continue
    else:
        for m in apps.get_models():
            try:
                if issubclass(m, ContentBase) and not m._meta.abstract:
                    models_list.append(m)
            except Exception:
                # Some proxy or special models may raise in issubclass checks
                pass
    return models_list


class PageContentInlineForm(forms.ModelForm):
    """
    Generic, future-proof selector: a single dropdown with all allowed
    content objects, regardless of their model.
    Value format: "app_label.model_name:pk".
    """

    content_item = forms.CharField(required=False, label="Контент")

    class Meta:
        model = PageContent
        fields = ()  # content_type/object_id derived via content_item

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attach autocomplete widget
        self.fields["content_item"].widget = ContentItemAutocompleteWidget()

        # Preselect current value for edit forms
        instance = getattr(self, "instance", None)
        if instance and instance.pk and instance.content_type_id and instance.object_id:
            ct = instance.content_type
            initial = f"{ct.app_label}.{ct.model}:{instance.object_id}"
            self.fields["content_item"].initial = initial
            # Ensure the initial label is rendered in widget
            widget = self.fields["content_item"].widget
            if hasattr(widget, "set_initial_display"):
                widget.set_initial_display(self._content_label(initial))

    def _content_label(self, value: str) -> str:
        try:
            left, object_id = value.split(":", 1)
            app_label, model_name = left.split(".", 1)
            model = apps.get_model(app_label, model_name)
            if model not in get_allowed_content_models():
                return ""
            obj = model.objects.filter(pk=object_id).first()
            if not obj:
                return ""
            return f"{model._meta.verbose_name.title()} | {obj}"
        except Exception:
            return ""

    def clean(self):
        cleaned = super().clean()
        # Skip validation for untouched extra inline forms
        if not self.has_changed():
            return cleaned
        value = cleaned.get("content_item")
        if not value:
            raise forms.ValidationError("Нужно выбрать существующий объект контента.")
        # Basic validation of the format
        try:
            left, object_id = value.split(":", 1)
            app_label, model_name = left.split(".", 1)
            object_id = int(object_id)
        except Exception:
            raise forms.ValidationError("Неверный формат выбора контента.")

        model = apps.get_model(app_label, model_name)
        if model not in get_allowed_content_models():
            raise forms.ValidationError("Выбранный тип контента не поддерживается.")
        # Ensure object exists
        if not model.objects.filter(pk=object_id).exists():
            raise forms.ValidationError("Выбранный объект не найден.")

        # Stash parsed values for save()
        self._parsed = (model, object_id)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        model, object_id = getattr(self, "_parsed", (None, None))
        if model is None:
            # When save() is called without valid clean(), re-parse from field
            value = self.cleaned_data.get("content_item")
            if value:
                left, object_id_str = value.split(":", 1)
                app_label, model_name = left.split(".", 1)
                model = apps.get_model(app_label, model_name)
                object_id = int(object_id_str)
        if model is not None:
            instance.content_type = ContentType.objects.get_for_model(model)
            instance.object_id = object_id
        if commit:
            instance.save()
        return instance


class ContentItemAutocompleteWidget(AutocompleteMixin, forms.Select):
    """Admin select2 widget for generic content search across allowed models.

    Selected value is a string "app_label.model_name:pk" and results are
    returned by a custom admin view.
    """

    url_name = "%s:pages_page_content_autocomplete"

    def __init__(self, attrs=None):
        # Create a lightweight field stub for AutocompleteMixin to fill attrs.
        field_stub = type("FieldStub", (), {})()
        field_stub.model = PageContent
        field_stub.name = "content_item"
        super().__init__(field=field_stub, admin_site=admin.site, attrs=attrs)
        self._initial_label = ""

    def set_initial_display(self, label: str):
        self._initial_label = label or ""

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        # These attributes are required by admin's autocomplete.js but aren't
        # used by our server endpoint.
        attrs.setdefault("data-app-label", "pages")
        attrs.setdefault("data-model-name", "pagecontent")
        attrs.setdefault("data-field-name", "content_item")
        return attrs

    def optgroups(self, name, value, attrs=None):
        default = (None, [], 0)
        groups = [default]
        values = value if isinstance(value, (list, tuple)) else [value]
        selected = [v for v in values if v]
        if selected:
            label = self._initial_label
            if not label and isinstance(selected[0], str):
                label = self._label_for_value(selected[0])
            default[1].append(
                self.create_option(
                    name, selected[0], label or selected[0], True, len(default[1])
                )
            )
        else:
            default[1].append(self.create_option(name, "", "", False, 0))
        return groups

    @staticmethod
    def _label_for_value(value: str) -> str:
        try:
            left, object_id = value.split(":", 1)
            app_label, model_name = left.split(".", 1)
            model = apps.get_model(app_label, model_name)
            if model not in get_allowed_content_models():
                return ""
            obj = model.objects.filter(pk=object_id).first()
            if not obj:
                return ""
            return f"{model._meta.verbose_name.title()} | {obj}"
        except Exception:
            return ""
