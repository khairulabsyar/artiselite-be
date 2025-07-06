import logging

from auditlog.context import set_actor

# Get the logger configured in settings.py
logger = logging.getLogger('audit_debug')

class AuditLogMixin:
    """
    A mixin for ViewSets to automatically set the actor for audit logs.
    It wraps the perform_create, perform_update, and perform_destroy methods
    to set the request.user as the actor within the auditlog context.
    """
    def perform_create(self, serializer):
        """
        Sets the actor and performs the create action.
        """
        with set_actor(self.request.user):
            serializer.save(_user=self.request.user, _reason="Created via API")

    def perform_update(self, serializer):
        """
        Sets the actor and performs the update action.
        """
        with set_actor(self.request.user):
            serializer.save(_user=self.request.user, _reason="Updated via API")

    def perform_destroy(self, instance):
        # Logs the user performing the action to the debug_audit.log file
        logger.debug(f"Setting actor in perform_destroy to: {self.request.user} (ID: {self.request.user.id if self.request.user else 'None'})")
        with set_actor(self.request.user):
            super().perform_destroy(instance)
