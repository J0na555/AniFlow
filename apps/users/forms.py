from django import forms

from apps.streaming.models import StreamingSource

from .models import UserSettings

_FIELD_CLASS = (
    "w-full bg-white/[0.03] border border-border rounded-2xl py-3 px-4 text-sm "
    "focus:outline-none focus:border-accent/50 focus:bg-white/[0.05] "
    "transition-all duration-300 accent-accent"
)


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ["preferred_source", "max_watching_limit", "ignore_watching_limit"]
        labels = {
            "preferred_source": "Preferred streaming source",
            "max_watching_limit": "Max simultaneous watching",
            "ignore_watching_limit": "Suppress watching-limit warnings",
        }
        help_texts = {
            "preferred_source": "Tried first when resolving watch links. Leave as no preference to use the default order.",
            "max_watching_limit": "0 turns the limit off. Above 0 enables a cap on how many series count toward watching.",
            "ignore_watching_limit": "When enabled, the dashboard will not show limit warnings after you dismiss them.",
        }
        widgets = {
            "preferred_source": forms.Select(attrs={"class": _FIELD_CLASS}),
            "max_watching_limit": forms.NumberInput(
                attrs={"class": _FIELD_CLASS, "min": 0}
            ),
            "ignore_watching_limit": forms.CheckboxInput(
                attrs={
                    "class": (
                        "w-4 h-4 rounded border-border bg-white/[0.03] "
                        "text-accent focus:ring-accent/40 focus:ring-offset-0"
                    )
                }
            ),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["preferred_source"]
        field.queryset = StreamingSource.objects.filter(is_active=True).order_by("name")
        field.empty_label = "No preference"
