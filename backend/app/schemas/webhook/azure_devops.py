"""
Webhook schema definitions for Azure DevOps integration.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, root_validator
from datetime import datetime


class WebhookAuthor(BaseModel):
    """Author information in Azure DevOps webhook."""
    id: str = Field(..., description="Author ID")
    displayName: str = Field(..., description="Author display name")
    uniqueName: str = Field(..., description="Author unique name or email")


class WebhookWorkItem(BaseModel):
    """Work item details in Azure DevOps webhook."""
    id: int = Field(..., description="Work item ID")
    rev: int = Field(..., description="Work item revision")
    fields: Dict[str, Any] = Field(..., description="Work item fields")
    url: str = Field(..., description="Work item URL")


class WebhookResource(BaseModel):
    """Resource section of Azure DevOps webhook."""
    id: int = Field(..., description="Resource ID")
    workItemId: int = Field(..., description="Work item ID")
    revision: Optional[Dict[str, Any]] = Field(None, description="Revision details")
    fields: Optional[Dict[str, Any]] = Field(None, description="Changed fields")
    url: str = Field(..., description="Resource URL")
    workItem: Optional[WebhookWorkItem] = Field(None, description="Work item details")
    
    @root_validator(pre=True)
    def extract_fields(cls, values):
        """Extract fields from revision if available."""
        if "revision" in values and values.get("revision") and "fields" in values["revision"]:
            values["fields"] = values["revision"]["fields"]
        return values


class WebhookPayload(BaseModel):
    """Azure DevOps webhook payload."""
    subscriptionId: str = Field(..., description="Subscription ID")
    notificationId: str = Field(..., description="Notification ID")
    id: str = Field(..., description="Event ID")
    eventType: str = Field(..., description="Event type")
    publisherId: str = Field(..., description="Publisher ID")
    message: Optional[Dict[str, Any]] = Field(None, description="Message details")
    detailedMessage: Optional[Dict[str, Any]] = Field(None, description="Detailed message")
    resource: WebhookResource = Field(..., description="Resource details")
    resourceVersion: str = Field(..., description="Resource version")
    resourceContainers: Dict[str, Any] = Field(..., description="Resource containers")
    createdDate: datetime = Field(..., description="Created date")
    
    @property
    def is_user_story(self) -> bool:
        """Check if the work item is a user story."""
        if not self.resource.fields:
            return False
        
        work_item_type = self.resource.fields.get("System.WorkItemType", "")
        return work_item_type.lower() in ["user story", "userstory", "pbi", "product backlog item"]
    
    @property
    def work_item_id(self) -> int:
        """Get the work item ID."""
        return self.resource.workItemId
    
    @property
    def work_item_title(self) -> Optional[str]:
        """Get the work item title."""
        if not self.resource.fields:
            return None
        return self.resource.fields.get("System.Title")
    
    @property
    def work_item_description(self) -> Optional[str]:
        """Get the work item description."""
        if not self.resource.fields:
            return None
        return self.resource.fields.get("System.Description")
    
    @property
    def work_item_acceptance_criteria(self) -> Optional[str]:
        """Get the work item acceptance criteria."""
        if not self.resource.fields:
            return None
            
        # Try different possible field names for acceptance criteria
        for field_name in [
            "Microsoft.VSTS.Common.AcceptanceCriteria",
            "System.AcceptanceCriteria",
            "Microsoft.VSTS.Requirements.AcceptanceCriteria"
        ]:
            if field_name in self.resource.fields:
                return self.resource.fields.get(field_name)
        
        return None


class WebhookResponse(BaseModel):
    """Response for webhook processing."""
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Status message")
    webhook_id: str = Field(..., description="Webhook ID")
    work_item_id: int = Field(..., description="Work item ID")
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    queued_for_processing: bool = Field(False, description="Whether the work item was queued for processing")
