from django.contrib import admin
from .models import Election, RegisteredVoter, VoteLedger, PreApprovedVoter


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    """
    Customizes the Admin view for the Election model.
    """
    list_display = ('name', 'election_id', 'is_active')
    search_fields = ('name', 'election_id')
    prepopulated_fields = {'election_id': ('name',)}  # Auto-fills the slug

@admin.register(PreApprovedVoter)
class PreApprovedVoterAdmin(admin.ModelAdmin):
    """
    Admin view for the pre-approved list.
    Allows manually adding/viewing single pre-approved voters.
    """
    list_display = ('unique_identifier', 'election', 'is_linked')
    list_filter = ('election', 'is_linked')
    search_fields = ('unique_identifier',)
    raw_id_fields = ('election',)
    readonly_fields = ('is_linked',)

@admin.register(RegisteredVoter)
class RegisteredVoterAdmin(admin.ModelAdmin):
    """
    Customizes the Admin view for the RegisteredVoter model.
    """
    list_display = ('voter_hash', 'election', 'has_voted')
    list_filter = ('election', 'has_voted')
    search_fields = ('voter_hash',)

    # Makes it easier to see/edit
    raw_id_fields = ('election',)


@admin.register(VoteLedger)
class VoteLedgerAdmin(admin.ModelAdmin):
    """
    Customizes the Admin view for the VoteLedger.
    This should be READ-ONLY. No one should edit the chain.
    """
    list_display = ('id', 'election', 'timestamp', 'previous_hash', 'current_hash')
    list_filter = ('election',)

    # --- CRITICAL: Make the ledger read-only in the admin ---
    def has_add_permission(self, request):
        return False  # No one can add votes via the admin

    def has_change_permission(self, request, obj=None):
        return False  # No one can change votes

    def has_delete_permission(self, request, obj=None):
        return False  # No one can delete votes