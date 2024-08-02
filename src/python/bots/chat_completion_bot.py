# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from botbuilder.core import ConversationState, TurnContext, UserState
from botbuilder.schema import ChannelAccount, Activity, ActivityTypes
from openai import AzureOpenAI

from data_models import ConversationData, ConversationTurn
from .state_management_bot import StateManagementBot
from utils import get_citations_card, replace_citations


class ChatCompletionBot(StateManagementBot):

    def __init__(self, conversation_state: ConversationState, user_state: UserState, aoai_client: AzureOpenAI):
        super().__init__(conversation_state, user_state)
        self._aoai_client = aoai_client

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome to the Chat Completion Bot!")

    async def on_message_activity(self, turn_context: TurnContext):
        # Get the state properties from the turn context.
        conversation_data = await self.conversation_data_accessor.get(
            turn_context, ConversationData([ConversationTurn(role="system", content=os.getenv("LLM_INSTRUCTIONS"))])
        )

        conversation_data.add_turn("user", turn_context.activity.text)

        extra_body = {}
        if os.getenv("AZURE_SEARCH_API_ENDPOINT"):
            extra_body['data_sources'] = [
                    {
                        "type": "azure_search",
                        "parameters": {
                            "endpoint": os.getenv("AZURE_SEARCH_API_ENDPOINT"),
                            "index_name": os.getenv("AZURE_SEARCH_INDEX"),
                            "authentication": {
                                "type": "system_assigned_managed_identity",
                            }
                        }
                    }
                ]

        completion = self._aoai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=conversation_data.toMessages(),
            extra_body=extra_body
        )

        response = completion.choices[0].message.content
        response = replace_citations(response)

        conversation_data.add_turn("assistant", response)
        await turn_context.send_activity(response)

        if 'citations' in completion.choices[0].message.context and len(completion.choices[0].message.context['citations']) > 0:
            citations = completion.choices[0].message.context['citations']
            await turn_context.send_activity(get_citations_card(citations))