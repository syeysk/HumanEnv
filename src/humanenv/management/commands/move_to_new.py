from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        from gardensunion.link.models import Link
        from db.models import (
            LinkHumanHuman,
        )

        for old_link in list(LinkHumanHuman.objects.all()):
            left_entity = old_link.human
            right_entity = old_link.huamn
            link = Link(
                left_code=left_entity.CODE,
                left_id=left_entity.pk,
                right_code=right_entity.CODE,
                right_id=right_entity.pk,
            )
            # link.save()

