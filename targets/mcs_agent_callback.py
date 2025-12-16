"""Microsoft Copilot Studio Agent callback target implementation."""

from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from microsoft.agents.core.models import ActivityTypes
from src.CopilotStudioClient import McsCopilotClient, McsConnectionSettings


@dataclass
class McsAgentConfig:
    """Configuration for Microsoft Copilot Studio Agent."""
    tenant_id: str
    app_client_id: str
    environment_id: str
    agent_identifier: str


class McsAgentCallbackTarget:
    """A Microsoft Copilot Studio Agent callback target."""
    
    def __init__(self, mcs_agent_config: McsAgentConfig):
        """Initialize with MCS Agent configuration."""
        self.mcs_agent_config = mcs_agent_config
    
    def create_callback(self) -> Callable:
        """Create an async callback function that uses MCS Agent."""
        
        async def mcs_agent_callback(
            messages: List,
            stream: Optional[bool] = False,  # noqa: ARG001
            session_state: Optional[str] = None,  # noqa: ARG001
            context: Optional[Dict[str, Any]] = None,  # noqa: ARG001
        ) -> Dict[str, List[Dict[str, str]]]:
            """Async callback that uses Microsoft Copilot Studio Agent to generate responses."""
            
            # Extract the latest message from the conversation history
            messages_list = [{"role": message.role, "content": message.content} for message in messages]
            latest_message = messages_list[-1]["content"]
            # print(f"Processing message: {latest_message}")
            
            try:
                # Create a connection settings object for the Copilot Studio client
                connection_settings = McsConnectionSettings(
                    tenant_id=self.mcs_agent_config.tenant_id,
                    app_client_id=self.mcs_agent_config.app_client_id,
                    environment_id=self.mcs_agent_config.environment_id,
                    agent_identifier=self.mcs_agent_config.agent_identifier,
                )
                
                # Initialize the Copilot Studio Client helper
                client = McsCopilotClient(connection_settings=connection_settings)
                
                # Start a conversation with the Copilot Studio agent
                await client.start_conversation_async()
                
                # Ask a question to the Copilot Studio agent
                activities = await client.ask_question_async(latest_message)
                
                # Extract content from response with validation
                content = "".join(
                    activity.text for activity in activities 
                    if activity.type == ActivityTypes.message
                )
                
                # Handle None or empty content
                if content is None or content == "":
                    content = "I cannot provide a response to this request."
                    print("Warning: MCS Agent returned None or empty content, using default message")
                
                # Format the response to follow the expected chat protocol format
                formatted_response = {
                    "content": content,
                    "role": "assistant"
                }
                
            except Exception as e:
                print(f"Error calling Microsoft Copilot Studio Agent: {e!s}")
                formatted_response = {
                    "content": "I encountered an error and couldn't process your request.",
                    "role": "assistant"
                }
            
            # Ensure content is never None before returning
            if formatted_response.get("content") is None:
                formatted_response["content"] = "No response available."
                print("Warning: Formatted response content was None, replaced with default")
            
            return {"messages": [formatted_response]}
        
        return mcs_agent_callback
    
    def get_target(self) -> Callable:
        """Get the target function for red team evaluation."""
        return self.create_callback()
