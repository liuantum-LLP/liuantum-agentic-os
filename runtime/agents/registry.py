def agent(slug: str, name: str, role: str, goal: str, tools: list[str], example_tasks: list[str]) -> dict:
    return {
        "slug": slug,
        "name": name,
        "role": role,
        "goal": goal,
        "purpose": goal,
        "instructions": f"Create useful local MVP outputs for: {goal}. Keep every external action draft-only and approval-aware.",
        "personality": "calm, practical, precise, and approval-aware",
        "tools": tools,
        "permissions": {"mode": "safe", "external_actions": "approval_required"},
        "capabilities": example_tasks,
        "example_tasks": example_tasks,
    }


BUILT_IN_AGENTS = [
    agent(
        "content-creator-agent",
        "Content Creator Agent",
        "Content Creator",
        "Generate complete content packages for social media, marketing, education, YouTube, ads, reels, blogs, and campaigns.",
        ["document_tool", "file_tool", "browser_tool", "image_generation_tool", "video_generation_tool", "social_tool"],
        ["Create a 7-day campaign", "Create LinkedIn posts", "Repurpose a blog into social content"],
    ),
    agent("social-media-manager-agent", "Social Media Manager Agent", "Social Media Manager", "Plan, draft, schedule, and analyze safe social content.", ["social_tool", "file_tool"], ["Create a content calendar", "Draft replies to comments"]),
    agent("email-assistant-agent", "Email Assistant Agent", "Email Assistant", "Summarize inboxes, draft replies, and extract tasks without sending mail.", ["email_tool", "file_tool"], ["Draft a reply", "Summarize priority emails"]),
    agent("automation-builder-agent", "Automation Builder Agent", "Automation Builder", "Turn natural language requests into approval-aware automation definitions.", ["automation_tool", "file_tool"], ["Create a weekly report automation"]),
    agent("brand-strategist-agent", "Brand Strategist Agent", "Brand Strategist", "Create brand voice, positioning, audience research, and campaign direction.", ["document_tool", "file_tool"], ["Create a brand tone guide"]),
    agent("video-creator-agent", "Video Creator Agent", "Video Creator", "Create scripts, scenes, prompts, storyboards, and video generation jobs.", ["video_generation_tool", "file_tool"], ["Create a launch storyboard"]),
    agent("image-creator-agent", "Image Creator Agent", "Image Creator", "Create image prompts, posters, thumbnails, ad creatives, and image generation jobs.", ["image_generation_tool", "file_tool"], ["Create a poster prompt package"]),
    agent("marketing-agent", "Marketing Agent", "Marketing Strategist", "Create campaign plans, captions, WhatsApp promos, and ad copy.", ["document_tool", "social_tool", "file_tool"], ["Create campaign for Python course"]),
    agent("personal-assistant-agent", "Personal Assistant Agent", "Personal Assistant", "Create daily plans, task lists, and reminder-style plans.", ["document_tool", "file_tool"], ["Plan my day"]),
    agent("front-desk-management-agent", "Front Desk Management Agent", "Front Desk Manager", "Create enquiry replies, call scripts, and admission follow-up messages.", ["document_tool", "file_tool"], ["Reply to Java course enquiry"]),
    agent("coding-agent", "Coding Agent", "Coding Planner", "Create project plans, file structures, implementation steps, and safe command suggestions.", ["file_tool", "document_tool"], ["Plan a Flask CRUD project"]),
    agent("business-analyst-agent", "Business Analyst Agent", "Business Analyst", "Create BRD/FRD outlines, user stories, and workflow steps.", ["document_tool", "file_tool"], ["Draft BRD for admissions CRM"]),
    agent("sales-agent", "Sales Agent", "Sales Assistant", "Create sales scripts, follow-up messages, and objection handling.", ["document_tool", "file_tool"], ["Create sales script for AI course"]),
    agent("hr-agent", "HR Agent", "HR Assistant", "Create job descriptions, interview questions, and onboarding checklists.", ["document_tool", "file_tool"], ["Create JD for Python trainer"]),
    agent("customer-support-agent", "Customer Support Agent", "Support Assistant", "Create FAQs, support replies, and troubleshooting scripts.", ["document_tool", "file_tool"], ["Handle login issue complaint"]),
    agent("tutor-agent", "Tutor Agent", "Tutor", "Create lesson plans, quizzes, assignments, and project ideas.", ["document_tool", "file_tool"], ["Teach Flask basics"]),
]


def list_agents() -> list[dict]:
    from runtime.agents.profiles import AgentProfileManager

    return AgentProfileManager().list()
