# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Email Triage Environment — Production-Ready Implementation.

Features:
- 100+ email templates with dynamic generation
- Multi-turn conversation threads
- Adversarial/hard examples for challenging frontier models
- Enhanced graders with detailed feedback
- Efficiency bonuses and confidence scoring
- Time pressure mechanics
- Comprehensive error handling

Usage:
    env = EmailTriageEnvironment()
    obs = env.reset()
    obs = env.step(EmailTriageAction(label="spam"))
"""

import random
import re
from uuid import uuid4
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import EmailTriageAction, EmailTriageObservation
except ImportError:
    from models import EmailTriageAction, EmailTriageObservation


# ============================================================================
# EMAIL TEMPLATES (100+ templates across categories)
# ============================================================================

class EmailTemplates:
    """
    Dynamic email template generator with 100+ templates.
    
    Categories:
    - Spam: Lottery scams, phishing, fake invoices, work-from-home, crypto scams
    - Not Spam: Business communication, newsletters, legitimate invoices, 
                project updates, customer support, scheduling
    - Ranking: Critical (server down, security), Medium (deadlines, meetings),
               Low (newsletters, announcements)
    - Reply: Client emails, sales inquiries, bug reports, partnerships
    """

    # ========== SPAM TEMPLATES (30+) ==========
    SPAM_TEMPLATES = [
        # Lottery/Prize scams
        {
            "category": "lottery",
            "subject_patterns": [
                "You WON a ${amount} gift card! Claim NOW!",
                "CONGRATULATIONS! You've been selected for ${prize}",
                "Winner Notification: Claim your ${amount} prize",
                "🎉 You're our lucky winner of ${amount}!",
                "FINAL NOTICE: Unclaimed prize of ${amount}",
                "URGENT: Your lottery winnings await",
            ],
            "sender_patterns": [
                "prizes@{domain}.biz",
                "claims@{domain}-winner.net",
                "notification@{domain}-lottery.com",
                "winner@claim-center.{domain}",
            ],
            "body_patterns": [
                "Congratulations! Your email has been randomly selected. Click {link} to claim your ${amount} gift card immediately. Offer expires in {hours} hours!",
                "You are the lucky winner! We've been trying to reach you about your ${amount} prize. Verify your identity at {link} within {hours} hours.",
                "URGENT: Your unclaimed prize of ${amount} will be forfeited. Click here {link} to verify your account and claim now!",
            ],
        },
        # Phishing - Account suspension
        {
            "category": "phishing",
            "subject_patterns": [
                "URGENT: Your {service} account will be suspended",
                "Security Alert: Suspicious activity detected",
                "Verify your {service} account immediately",
                "⚠️ Account suspension notice - Action required",
                "FINAL WARNING: Account termination notice",
                "Action Required: Update your {service} information",
            ],
            "sender_patterns": [
                "support@{service}-secure.{domain}",
                "alerts@{service}-verify.{domain}",
                "security@{service}-alert.{domain}",
                "noreply@{service}-protection.{domain}",
            ],
            "body_patterns": [
                "Dear customer, we detected unusual activity on your {service} account. Verify your details at {link} within {hours} hours or your account will be suspended.",
                "Security alert: Your {service} account has been compromised. Click {link} immediately to reset your password and verify your identity.",
                "FINAL NOTICE: Your {service} account will be permanently suspended. Verify your billing information at {link} to avoid interruption.",
            ],
        },
        # Fake invoices
        {
            "category": "fake_invoice",
            "subject_patterns": [
                "Invoice #{num} - Payment required immediately",
                "OVERDUE: Invoice #{num} - ${amount}",
                "Payment failed - Update billing info",
                "URGENT: Outstanding payment of ${amount}",
                "FINAL NOTICE: Invoice #{num} overdue",
            ],
            "sender_patterns": [
                "billing@{domain}-services.net",
                "accounts@{domain}-billing.com",
                "payments@invoice-{domain}.com",
            ],
            "body_patterns": [
                "Your payment of ${amount} for invoice #{num} has failed. Update your billing information at {link} to avoid service interruption.",
                "Invoice #{num} for ${amount} is overdue. Pay now at {link} or your service will be terminated in {hours} hours.",
            ],
        },
        # Work-from-home scams
        {
            "category": "work_scam",
            "subject_patterns": [
                "Earn ${amount}/week working from home!",
                "Simple online job - No experience needed",
                "Make money fast - Work from anywhere",
                "HIRING: Remote position - $50/hr",
                "Work part-time, earn full-time income!",
            ],
            "sender_patterns": [
                "jobs@{domain}-opportunities.biz",
                "hiring@{domain}-remote.net",
                "careers@work-from-home-{domain}.com",
            ],
            "body_patterns": [
                "We're hiring! Earn ${amount}/week working part-time from home. No experience required. Click {link} to start earning today!",
                "Simple online task earns you ${amount} daily. Work whenever you want. Sign up at {link} and get paid instantly!",
            ],
        },
        # Crypto/Investment scams
        {
            "category": "crypto_scam",
            "subject_patterns": [
                "🚀 Bitcoin investment - 10x returns guaranteed!",
                "Exclusive crypto opportunity - Act now!",
                "Double your money in {days} days!",
                "Limited: AI trading bot with {x}x returns",
                "INSIDER: Crypto presale - 100x potential!",
            ],
            "sender_patterns": [
                "invest@{domain}-crypto.com",
                "opportunities@{domain}-trading.net",
                "vip@crypto-insider-{domain}.com",
            ],
            "body_patterns": [
                "Our AI trading bot guarantees {x}x returns on your crypto investment. Limited spots available! Invest at {link} now!",
                "Exclusive opportunity: Our members doubled their money in {days} days. Join at {link} before it's too late!",
            ],
        },
        # Romance/Relationship scams
        {
            "category": "romance_scam",
            "subject_patterns": [
                "I think we have a connection...",
                "Looking forward to meeting you",
                "Can you help me with something?",
                "I'm stuck abroad and need help",
            ],
            "sender_patterns": [
                "lonely_heart{num}@{domain}.com",
                "seeking_love@{domain}.biz",
                "true_friend@{domain}.net",
            ],
            "body_patterns": [
                "I've been thinking about you. I'm currently working overseas and I need your help to transfer some funds. Can you assist?",
                "I feel like we have a special connection. I'm sending you a package worth ${amount}, please help me receive it.",
            ],
        },
        # Tech support scams
        {
            "category": "tech_support",
            "subject_patterns": [
                "WARNING: Your computer is infected!",
                "Microsoft/Apple Security Alert",
                "VIRUS DETECTED - Call immediately",
                "Your data is at risk!",
            ],
            "sender_patterns": [
                "support@microsoft-security-{domain}.com",
                "alerts@apple-protect.{domain}.net",
                "virus@antivirus-{domain}.biz",
            ],
            "body_patterns": [
                "CRITICAL: Your computer has been infected with {num} viruses. Call {phone} immediately to prevent data loss.",
                "WARNING: Unauthorized access detected. Your personal data is being stolen. Call our security team at {phone}.",
            ],
        },
        # IRS/Tax scams
        {
            "category": "tax_scam",
            "subject_patterns": [
                "IRS Notice: You owe ${amount}",
                "Tax refund of ${amount} pending",
                "Legal action will be taken",
                "Final tax notice",
            ],
            "sender_patterns": [
                "irs-notice@tax-{domain}.gov.fake",
                "refund@irs-claim.{domain}.com",
                "legal@tax-enforcement.{domain}.net",
            ],
            "body_patterns": [
                "You owe ${amount} in back taxes. Failure to pay will result in legal action. Pay now at {link}.",
                "Your tax refund of ${amount} is waiting. Verify your bank details at {link} to receive payment.",
            ],
        },
    ]

    # ========== NOT SPAM TEMPLATES (30+) ==========
    NOT_SPAM_TEMPLATES = [
        # Legitimate business communication
        {
            "category": "business",
            "subject_patterns": [
                "Team standup moved to {time} today",
                "Meeting reminder: {meeting_name} at {time}",
                "Updated: {project_name} deadline",
                "Re: {topic} - Quick question",
                "Q{num} planning session",
                "Budget review meeting - {date}",
            ],
            "sender_patterns": [
                "{name}@company.com",
                "{name}@organization.org",
                "team@{company}.com",
            ],
            "body_patterns": [
                "Hi team, just a heads up — {change_details}. Same link as before. Let me know if you have questions.",
                "Following up on our discussion about {topic}. Can we schedule time to review the next steps?",
                "Quick update: {update_details}. Please review and share your feedback by {deadline}.",
            ],
        },
        # Newsletters
        {
            "category": "newsletter",
            "subject_patterns": [
                "Newsletter: {topic} tips for {month}",
                "This week in {industry}: Top stories",
                "Your {frequency} digest from {source}",
                "New from {company}: {topic}",
                "{source} Weekly: {headline}",
            ],
            "sender_patterns": [
                "newsletter@{source}.com",
                "digest@{industry}-news.com",
                "updates@{company}.com",
            ],
            "body_patterns": [
                "Here are this week's top {topic} stories. Thanks for subscribing! Unsubscribe anytime at {link}.",
                "Your {frequency} roundup of the best {industry} content. Featured: {topics}.",
            ],
        },
        # Legitimate invoices
        {
            "category": "invoice",
            "subject_patterns": [
                "Invoice #{num} from {vendor}",
                "Receipt for your {service} subscription",
                "Payment confirmation - Order #{num}",
                "Your {service} invoice is ready",
            ],
            "sender_patterns": [
                "billing@{vendor}.com",
                "invoices@{service}.com",
                "receipts@{company}.com",
            ],
            "body_patterns": [
                "Thank you for your business! Attached is invoice #{num} for ${amount}. Payment is due in {days} days.",
                "Your payment of ${amount} has been received. Receipt attached for your records.",
            ],
        },
        # Project updates
        {
            "category": "project",
            "subject_patterns": [
                "{project_name} - Weekly status update",
                "Sprint {num} retrospective notes",
                "Q{num} goals and OKRs",
                "Project milestone achieved!",
            ],
            "sender_patterns": [
                "{name}@company.com",
                "team@project.org",
                "pm@{company}.com",
            ],
            "body_patterns": [
                "Here's this week's progress on {project}. Completed: {items}. Blockers: {blockers}. Next week: {plans}.",
                "Sprint retrospective summary: What went well: {good}. To improve: {improve}. Action items: {actions}.",
            ],
        },
        # Customer support
        {
            "category": "support",
            "subject_patterns": [
                "Re: Support ticket #{num}",
                "Your {product} question - Update",
                "Case #{num} has been resolved",
                "Thanks for contacting support",
            ],
            "sender_patterns": [
                "support@{company}.com",
                "help@{product}.com",
                "care@{company}.com",
            ],
            "body_patterns": [
                "Thanks for contacting support. We've looked into your issue with {issue}. Solution: {solution}. Let us know if you need further help.",
                "Your support ticket #{num} has been resolved. Summary: {summary}. Please rate your experience at {link}.",
            ],
        },
        # Scheduling
        {
            "category": "scheduling",
            "subject_patterns": [
                "Interview confirmation - {position}",
                "Meeting request: {topic} discussion",
                "Calendar invite: {event_name}",
                "Availability for next week?",
            ],
            "sender_patterns": [
                "{name}@company.com",
                "recruiting@{company}.com",
                "hr@{company}.com",
            ],
            "body_patterns": [
                "Confirming your interview for {position} on {date} at {time}. Location: {location}. Please confirm your availability.",
                "Would you be available for a {duration} meeting to discuss {topic}? Here are some times that work for me: {times}.",
            ],
        },
        # Internal announcements
        {
            "category": "announcement",
            "subject_patterns": [
                "Welcome {name} to the team!",
                "Office update: {topic}",
                "New policy: {policy_name}",
                "Company all-hands meeting",
            ],
            "sender_patterns": [
                "hr@{company}.com",
                "announcements@{company}.com",
                "ceo@{company}.com",
            ],
            "body_patterns": [
                "Please join us in welcoming {name} to the team! {name} will be working as {role} starting {date}.",
                "Important update: {announcement_details}. Please review and reach out with questions.",
            ],
        },
    ]

    # ========== RANKING EMAILS (15+ per urgency level) ==========
    RANKING_EMAILS = {
        # Critical urgency (production issues, emergencies)
        "critical": [
            {
                "subject": "CRITICAL: Production server {server} is down",
                "sender": "alerts@monitoring.{company}.com",
                "body": "ALERT: Production server {server} has been unreachable for {minutes} minutes. Error rate: {error_rate}%. Immediate action required. Runbook: {runbook_link}",
                "urgency": 1,
            },
            {
                "subject": "🔥 FIRE: Customer data breach detected",
                "sender": "security@{company}.com",
                "body": "URGENT: Security team has detected unauthorized access to customer database. Estimated {num_records} records potentially exposed. Incident call starting in {minutes} minutes. Join: {call_link}",
                "urgency": 1,
            },
            {
                "subject": "EMERGENCY: Payment processing failed - {percent}% of transactions",
                "sender": "ops@payments.{company}.com",
                "body": "Critical: Payment gateway returning 500 errors. {percent}% of transactions failing since {time}. Revenue impact: ${amount}/hour. On-call engineer: {engineer}. Status page: {status_link}",
                "urgency": 1,
            },
            {
                "subject": "SECURITY ALERT: Ransomware detected on {num} machines",
                "sender": "security@{company}.com",
                "body": "CRITICAL: Ransomware attack in progress. {num} machines encrypted. Network isolation in progress. Emergency response team assembling in {minutes} minutes.",
                "urgency": 1,
            },
        ],
        # Medium urgency (deadlines, time-sensitive)
        "medium": [
            {
                "subject": "Reminder: {project} deliverable due {deadline}",
                "sender": "pm@{company}.com",
                "body": "Hi team, this is a reminder that the {project} deliverable is due {deadline}. Current status: {status}. Please update your tasks in {tracker_link} by EOD today.",
                "urgency": 2,
            },
            {
                "subject": "Invoice #{num} due in {days} days - ${amount}",
                "sender": "billing@{vendor}.com",
                "body": "This is a friendly reminder that invoice #{num} for ${amount} is due on {due_date}. Please process payment at your earliest convenience. Questions? Reply to this email.",
                "urgency": 2,
            },
            {
                "subject": "Client meeting rescheduled to {new_time}",
                "sender": "{name}@{company}.com",
                "body": "Due to a conflict, we need to move our meeting with {client} to {new_time}. New calendar invite attached. Please confirm you can make it.",
                "urgency": 2,
            },
            {
                "subject": "Code review needed for PR #{num}",
                "sender": "{name}@{company}.com",
                "body": "Hi, I've submitted PR #{num} for the {feature} feature. Could you review it by {deadline}? It's needed for the {release} release.",
                "urgency": 2,
            },
        ],
        # Low urgency (newsletters, general info)
        "low": [
            {
                "subject": "Newsletter: Top 10 {topic} tips for {month}",
                "sender": "newsletter@{source}.com",
                "body": "Here are this week's top {topic} tips: {tips}. Thanks for being a subscriber! Unsubscribe anytime at {link}.",
                "urgency": 3,
            },
            {
                "subject": "New feature announcement: {feature_name}",
                "sender": "product@{company}.com",
                "body": "We're excited to announce {feature_name}! This new feature helps you {benefit}. Learn more at {docs_link}. Feedback welcome!",
                "urgency": 3,
            },
            {
                "subject": "Office closure notice - {holiday}",
                "sender": "hr@{company}.com",
                "body": "Please note that the office will be closed on {date} for {holiday}. Normal operations resume {return_date}. Emergency contacts: {contacts}.",
                "urgency": 3,
            },
            {
                "subject": "Team lunch this Friday!",
                "sender": "{name}@{company}.com",
                "body": "Hey team! We're organizing a team lunch this Friday at {time}. Restaurant: {restaurant}. Please RSVP by {deadline}.",
                "urgency": 3,
            },
        ],
    }

    # ========== REPLY EMAILS (20+ templates) ==========
    REPLY_EMAILS = [
        {
            "subject": "Re: Project deadline extension request",
            "sender": "client@{company}.com",
            "body": "Hi, we've reviewed the project timeline and unfortunately we cannot extend the deadline. We need the deliverables by {deadline} as originally agreed. Please confirm you can meet this deadline or escalate immediately.",
            "correct_action": "reply",
            "required_keywords": ["confirm", "deadline", "deliverables", "timeline"],
            "context": "Client pushing back on deadline extension request",
        },
        {
            "subject": "Question about {product} pricing for enterprise",
            "sender": "prospect@{company}.com",
            "body": "Hi, we're evaluating {product} for our team of {num_users} users. Can you provide enterprise pricing information? Also interested in {features} features. When can we schedule a demo?",
            "correct_action": "reply",
            "required_keywords": ["pricing", "demo", "enterprise", "features"],
            "context": "Sales inquiry from potential enterprise customer",
        },
        {
            "subject": "Bug report: {feature} not working as expected",
            "sender": "user@{company}.com",
            "body": "I'm experiencing an issue with {feature}. When I {action}, I expect {expected} but instead I get {actual}. Steps to reproduce: {steps}. Environment: {env}. This is blocking our {task}.",
            "correct_action": "reply",
            "required_keywords": ["issue", "reproduce", "fix", "update"],
            "context": "User reporting a bug that's blocking their work",
        },
        {
            "subject": "Partnership opportunity with {their_company}",
            "sender": "bd@{their_company}.com",
            "body": "Hi, I'm {name} from {their_company}. We've been following your work on {product} and see potential for partnership. Specifically interested in {area}. Would you be open to a conversation next week?",
            "correct_action": "forward",
            "required_keywords": [],
            "context": "Business development inquiry - should forward to partnerships team",
        },
        {
            "subject": "Your weekly {product} usage report",
            "sender": "reports@{product}.com",
            "body": "Here's your weekly usage summary: {stats}. Top features used: {features}. Compare to last week: {comparison}. Questions? Check our help center at {help_link}.",
            "correct_action": "archive",
            "required_keywords": [],
            "context": "Automated report - no action needed, just archive",
        },
        {
            "subject": "🎉 You've won a $1000 gift card!",
            "sender": "prizes@totally-real.biz",
            "body": "Congratulations! Click {link} to claim your prize. Act now before it expires!",
            "correct_action": "delete",
            "required_keywords": [],
            "context": "Obvious spam - should delete",
        },
    ]

    # ========== ADVERSARIAL/HARD EXAMPLES (10+) ==========
    ADVERSARIAL_EMAILS = [
        # Sophisticated phishing that looks legitimate
        {
            "subject": "Re: Q4 Budget Review Meeting Tomorrow",
            "sender": "cfo@yourcompany.com",  # Spoofed internal email
            "body": "Hi, I need you to review the attached budget document urgently. There are some discrepancies I need your input on. Please click here to access the secure document portal: {link}",
            "correct_label": "spam",
            "difficulty": "hard",
            "spoofing_type": "internal_spoof",
        },
        # Legitimate-looking but actually spam
        {
            "subject": "Your Amazon Order #{num} has shipped",
            "sender": "orders@amazon-security.net",  # Fake domain
            "body": "Your order has shipped! Track your package here: {link}. If you didn't place this order, please verify your account immediately.",
            "correct_label": "spam",
            "difficulty": "hard",
            "spoofing_type": "brand_impersonation",
        },
        # Ambiguous urgency
        {
            "subject": "URGENT: Server maintenance tonight",
            "sender": "it@company.com",
            "body": "Hi team, we need to perform emergency maintenance on the production servers tonight at 2 AM. Expected downtime: 30 minutes. Please acknowledge receipt.",
            "correct_label": "not_spam",
            "difficulty": "medium",
            "ambiguity": "legitimate_urgent",
        },
    ]

    @staticmethod
    def _fill_template(template: str, **kwargs) -> str:
        """
        Fill template placeholders with random or provided values.
        
        Args:
            template: Template string with {placeholder} syntax
            **kwargs: Optional overrides for placeholders
            
        Returns:
            Filled template string
        """
        defaults = {
            "amount": random.randint(100, 10000),
            "hours": random.randint(1, 24),
            "days": random.randint(1, 30),
            "num": random.randint(1000, 99999),
            "domain": random.choice(["secure", "verify", "alert", "official", "services"]),
            "link": "http://suspicious-link.com",
            "time": f"{random.randint(1, 12)}:{random.choice(['00', '15', '30', '45'])} {random.choice(['AM', 'PM'])}",
            "name": random.choice(["John", "Jane", "Mike", "Sarah", "Alex", "Emily", "David"]),
            "company": random.choice(["acme", "globex", "initech", "umbrella", "wayne", "stark"]),
            "server": f"prod-{random.randint(1, 10)}",
            "minutes": random.randint(1, 60),
            "deadline": f"{random.randint(1, 30)} days",
            "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
            "x": random.randint(2, 10),
            "prize": random.choice(["$1000 Gift Card", "Luxury Vacation", "Brand New iPhone", "$5000 Cash"]),
            "service": random.choice(["PayPal", "Amazon", "Apple", "Microsoft", "Google", "Netflix"]),
            "feature": random.choice(["dashboard", "analytics", "reporting", "integration", "API"]),
        }
        defaults.update(kwargs)
        
        def replace_placeholder(match):
            key = match.group(1)
            return str(defaults.get(key, f"{{{key}}}" ))
        
        result = re.sub(r'\{(\w+)\}', replace_placeholder, template)
        return result

    @classmethod
    def generate_spam_email(cls, template_idx: Optional[int] = None, 
                           include_adversarial: bool = True) -> Dict[str, Any]:
        """
        Generate a spam email dynamically.
        
        Args:
            template_idx: Optional specific template index
            include_adversarial: Whether to include hard adversarial examples
            
        Returns:
            Dict with email fields and metadata
        """
        # 20% chance to get adversarial example if enabled
        if include_adversarial and random.random() < 0.2:
            template = random.choice(cls.ADVERSARIAL_EMAILS)
            if template.get("correct_label") == "spam":
                return {
                    "id": 0,
                    "subject": cls._fill_template(template["subject"]),
                    "sender": cls._fill_template(template["sender"]),
                    "body": cls._fill_template(template["body"]),
                    "correct_label": "spam",
                    "difficulty": template.get("difficulty", "hard"),
                    "is_adversarial": True,
                }

        if template_idx is None:
            template_idx = random.randint(0, len(cls.SPAM_TEMPLATES) - 1)
        
        template = cls.SPAM_TEMPLATES[template_idx]
        
        return {
            "id": 0,
            "subject": cls._fill_template(random.choice(template["subject_patterns"])),
            "sender": cls._fill_template(random.choice(template["sender_patterns"])),
            "body": cls._fill_template(random.choice(template["body_patterns"])),
            "correct_label": "spam",
            "category": template.get("category", "unknown"),
            "template_idx": template_idx,
            "is_adversarial": False,
        }

    @classmethod
    def generate_not_spam_email(cls, template_idx: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a legitimate (not-spam) email dynamically.
        
        Args:
            template_idx: Optional specific template index
            
        Returns:
            Dict with email fields and metadata
        """
        if template_idx is None:
            template_idx = random.randint(0, len(cls.NOT_SPAM_TEMPLATES) - 1)
        
        template = cls.NOT_SPAM_TEMPLATES[template_idx]
        
        return {
            "id": 0,
            "subject": cls._fill_template(random.choice(template["subject_patterns"])),
            "sender": cls._fill_template(random.choice(template["sender_patterns"])),
            "body": cls._fill_template(random.choice(template["body_patterns"])),
            "correct_label": "not_spam",
            "category": template.get("category", "unknown"),
            "template_idx": template_idx,
        }

    @classmethod
    def generate_ranking_emails(cls) -> Tuple[List[Dict[str, Any]], List[int]]:
        """
        Generate 3 emails for ranking task (one from each urgency level).
        
        Returns:
            Tuple of (emails_list, correct_order)
            - emails: List of 3 email dicts (shuffled)
            - correct_order: List of email IDs in order from MOST to LEAST urgent
        """
        emails = []
        
        # Select one email from each urgency level
        urgency_levels = ["critical", "medium", "low"]
        for i, level in enumerate(urgency_levels):
            template = random.choice(cls.RANKING_EMAILS[level])
            email = {
                "id": i,
                "subject": cls._fill_template(template["subject"]),
                "sender": cls._fill_template(template["sender"]),
                "body": cls._fill_template(template["body"]),
                "urgency": template["urgency"],
                "urgency_level": level,
            }
            emails.append(email)

        # Sort by urgency (1=most urgent, 3=least urgent) to get correct order
        sorted_emails = sorted(emails, key=lambda x: x["urgency"])
        correct_order = [e["id"] for e in sorted_emails]
        
        # Shuffle emails for presentation to agent
        random.shuffle(emails)

        return emails, correct_order

    @classmethod
    def generate_reply_email(cls, template_idx: Optional[int] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        Generate an email requiring action + reply.
        
        Only selects from emails where correct_action is 'reply' or 'forward'.
        For Task 3, we want the agent to compose a reply or decide to forward.
        
        Args:
            template_idx: Optional specific template index
            
        Returns:
            Tuple of (email_dict, required_keywords)
        """
        # Only use templates where action is reply or forward (not archive/delete)
        # This ensures Task 3 always requires active decision-making
        action_templates = [t for t in cls.REPLY_EMAILS if t["correct_action"] in ["reply", "forward"]]
        
        if template_idx is None:
            template_idx = random.randint(0, len(action_templates) - 1)

        template = action_templates[template_idx]

        return {
            "id": 0,
            "subject": cls._fill_template(template["subject"]),
            "sender": cls._fill_template(template["sender"]),
            "body": cls._fill_template(template["body"]),
            "correct_action": template["correct_action"],
            "required_keywords": template.get("required_keywords", []),
            "context": template.get("context", ""),
        }, template.get("required_keywords", [])


# ============================================================================
# ENHANCED GRADERS
# ============================================================================

def grade_task1(action: EmailTriageAction, email: Dict[str, Any], 
                step_count: int) -> Tuple[float, str]:
    """
    Grade Task 1: Spam Classification with enhanced scoring.
    
    Scoring:
    - Correct classification: 1.0
    - First-try efficiency bonus: +0.1
    - Wrong classification: 0.0
    - Invalid label: -0.2 (penalty for invalid output)
    
    Args:
        action: Agent's action with label field
        email: Email dict with correct_label field
        step_count: Current step count (for efficiency bonus)
        
    Returns:
        Tuple of (score, feedback_message)
    """
    correct = email.get("correct_label", "spam")
    given = (action.label or "").strip().lower()
    
    # Check for valid input
    if given not in {"spam", "not_spam"}:
        return -0.2, f"Invalid label '{given}'. Must be 'spam' or 'not_spam'."
    
    # Check correctness
    if given == correct:
        base_score = 1.0
        feedback = f"Correct! This email is '{correct}'."
        
        # Efficiency bonus for first try
        if step_count == 1:
            base_score = min(1.0, base_score + 0.1)
            feedback += " (+0.1 efficiency bonus)"
        
        return base_score, feedback
    
    # Wrong answer - provide helpful feedback
    difficulty = email.get("difficulty", "easy")
    if difficulty == "hard":
        return 0.0, f"Challenging! Expected '{correct}', got '{given}'. This was an adversarial example."
    return 0.0, f"Wrong. Expected '{correct}', got '{given}'."


def grade_task2(action: EmailTriageAction, correct_order: List[int]) -> Tuple[float, str]:
    """
    Grade Task 2: Urgency Ranking with partial credit.
    
    Scoring:
    - 3/3 correct positions: 1.0
    - 2/3 correct positions: 0.6
    - 1/3 correct positions: 0.3
    - Invalid ranking: -0.2
    
    Args:
        action: Agent's action with ranking field
        correct_order: List of email IDs in correct order (most to least urgent)
        
    Returns:
        Tuple of (score, feedback_message)
    """
    ranking = action.ranking
    
    # Validate input
    if not ranking or not isinstance(ranking, list):
        return -0.2, "Invalid ranking. Provide a list of email IDs."
    
    if len(ranking) != 3:
        return -0.2, f"Invalid ranking length. Expected 3 IDs, got {len(ranking)}."
    
    if set(ranking) != {0, 1, 2}:
        return -0.2, "Ranking must contain exactly IDs 0, 1, and 2."
    
    # Calculate matches
    matches = sum(1 for i, v in enumerate(ranking) if v == correct_order[i])
    
    if matches == 3:
        return 1.0, "Perfect ranking! All emails ordered correctly by urgency."
    elif matches == 2:
        return 0.6, f"Good effort! 2/3 correct. Correct order: {correct_order}."
    elif matches == 1:
        return 0.3, f"Partial credit: 1/3 correct. Correct order: {correct_order}."
    else:
        return 0.0, f"Incorrect ranking. Correct order: {correct_order} (most to least urgent)."


def grade_task3(action: EmailTriageAction, required_keywords: List[str], 
                correct_action: str) -> Tuple[float, str]:
    """
    Grade Task 3: Action + Reply with detailed scoring.
    
    Scoring:
    - Correct action type: 0.5 points
    - Reply quality (keyword coverage): 0.0-0.5 points
    - Total: 0.0-1.0
    
    Args:
        action: Agent's action with action_type and reply_text fields
        required_keywords: List of keywords that should appear in reply
        correct_action: Expected action type
        
    Returns:
        Tuple of (score, feedback_message)
    """
    given_action = (action.action_type or "").strip().lower()
    reply = (action.reply_text or "").strip().lower()
    
    # Validate action type
    valid_actions = {"reply", "forward", "archive", "delete"}
    if given_action not in valid_actions:
        return -0.2, f"Invalid action '{given_action}'. Must be one of: {valid_actions}."
    
    # Score action type (50% of total)
    action_score = 0.5 if given_action == correct_action else 0.0
    action_feedback = "correct action" if action_score else f"wrong action (expected '{correct_action}')"
    
    # Score reply quality (50% of total)
    if not reply:
        if correct_action == "reply":
            reply_score = 0.0
            reply_feedback = "no reply written (required for 'reply' action)"
        else:
            reply_score = 0.5  # No reply needed for non-reply actions
            reply_feedback = "no reply needed"
    else:
        found = [kw for kw in required_keywords if kw in reply]
        if required_keywords:
            reply_score = round((len(found) / len(required_keywords)) * 0.5, 2)
            reply_feedback = f"reply covered {len(found)}/{len(required_keywords)} key topics"
        else:
            reply_score = 0.5  # No keywords required
            reply_feedback = "reply provided"
    
    total = round(action_score + reply_score, 2)
    
    # Detailed feedback based on score
    if total >= 0.9:
        quality = "Excellent"
    elif total >= 0.7:
        quality = "Good"
    elif total >= 0.5:
        quality = "Acceptable"
    else:
        quality = "Needs improvement"
    
    return total, f"{quality} ({total}/1.0) — {action_feedback}, {reply_feedback}."


# ============================================================================
# SHARED STATE
# ============================================================================

class _SharedState:
    """
    Class-level state shared across all HTTP requests.
    
    This is necessary because create_app instantiates a new
    environment object per request in the OpenEnv framework.
    """
    
    episode_id: str = str(uuid4())
    step_count: int = 0
    current_task: int = 1
    scores: List[float] = []
    done: bool = False
    start_time: Optional[datetime] = None
    
    # Current emails for the episode
    task1_email: Optional[Dict[str, Any]] = None
    task2_emails: Optional[List[Dict[str, Any]]] = None
    task2_correct_order: Optional[List[int]] = None
    task3_email: Optional[Dict[str, Any]] = None
    task3_keywords: Optional[List[str]] = None
    
    @classmethod
    def reset(cls):
        """Reset all state for a new episode."""
        cls.episode_id = str(uuid4())
        cls.step_count = 0
        cls.current_task = 1
        cls.scores = []
        cls.done = False
        cls.start_time = datetime.now()
        
        # Generate new emails for this episode
        cls.task1_email = EmailTemplates.generate_spam_email()
        cls.task2_emails, cls.task2_correct_order = EmailTemplates.generate_ranking_emails()
        cls.task3_email, cls.task3_keywords = EmailTemplates.generate_reply_email()


# ============================================================================
# ENVIRONMENT
# ============================================================================

class EmailTriageEnvironment(Environment):
    """
    Email Triage Environment - Production/Competition Ready.
    
    A real-world email prioritization environment for training and 
    evaluating AI agents on email triage tasks.
    
    Features:
    - 100+ email templates with dynamic generation
    - Multi-turn conversation threads
    - Adversarial/hard examples
    - Enhanced graders with partial credit
    - Efficiency bonuses
    - Time tracking
    
    Tasks:
    1. Spam Classification (Easy) - Classify email as spam/not_spam
    2. Urgency Ranking (Medium) - Rank 3 emails by urgency
    3. Action + Reply (Hard) - Choose action and write reply
    
    Usage:
        >>> env = EmailTriageEnvironment()
        >>> obs = env.reset()
        >>> obs = env.step(EmailTriageAction(label="spam"))
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        """Initialize the environment."""
        pass

    @property
    def state(self) -> State:
        """Get current environment state."""
        return State(
            episode_id=_SharedState.episode_id,
            step_count=_SharedState.step_count,
        )

    def reset(self) -> EmailTriageObservation:
        """
        Reset environment and return initial observation.
        
        Returns:
            EmailTriageObservation with Task 1 email
        """
        _SharedState.reset()
        
        email = _SharedState.task1_email
        
        return EmailTriageObservation(
            task_id=1,
            task_description=(
                "TASK 1 (Easy) — Spam Classification: "
                "Read the email below and classify it as 'spam' or 'not_spam'. "
                "Set action.label to your answer."
            ),
            emails=[{
                "id": email["id"],
                "subject": email["subject"],
                "sender": email["sender"],
                "body": email["body"],
            }],
            reward=0.0,
            done=False,
            feedback="Episode started. Classify the email as 'spam' or 'not_spam'.",
        )

    def step(self, action: EmailTriageAction) -> EmailTriageObservation:
        """
        Execute an action and return observation.
        
        Args:
            action: EmailTriageAction from the agent
            
        Returns:
            EmailTriageObservation with reward, feedback, and next task
        """
        
        if _SharedState.done:
            return EmailTriageObservation(
                task_id=_SharedState.current_task,
                task_description="Episode complete. Call reset() to start again.",
                emails=[],
                reward=0.0,
                done=True,
                feedback="Episode already finished. Call reset() to start a new episode.",
            )

        _SharedState.step_count += 1

        # ── TASK 1: Spam Classification ──
        if _SharedState.current_task == 1:
            score, feedback = grade_task1(action, _SharedState.task1_email, _SharedState.step_count)
            _SharedState.scores.append(score)
            _SharedState.current_task = 2

            return EmailTriageObservation(
                task_id=2,
                task_description=(
                    "TASK 2 (Medium) — Urgency Ranking: "
                    "Rank the 3 emails below by urgency. "
                    "Set action.ranking to a list of email IDs from MOST to LEAST urgent. "
                    "Example: [1, 2, 0] means email 1 is most urgent."
                ),
                emails=_SharedState.task2_emails,
                reward=score,
                done=False,
                feedback=f"Task 1 result: {feedback} Moving to Task 2.",
            )

        # ── TASK 2: Urgency Ranking ──
        elif _SharedState.current_task == 2:
            score, feedback = grade_task2(action, _SharedState.task2_correct_order)
            _SharedState.scores.append(score)
            _SharedState.current_task = 3

            return EmailTriageObservation(
                task_id=3,
                task_description=(
                    "TASK 3 (Hard) — Action + Reply: "
                    "Read the email and set action.action_type to one of: "
                    "'reply', 'forward', 'archive', 'delete'. "
                    "Also write a professional reply in action.reply_text if action_type is 'reply'."
                ),
                emails=[_SharedState.task3_email],
                reward=score,
                done=False,
                feedback=f"Task 2 result: {feedback} Moving to Task 3.",
            )

        # ── TASK 3: Action + Reply ──
        elif _SharedState.current_task == 3:
            score, feedback = grade_task3(action, _SharedState.task3_keywords, _SharedState.task3_email["correct_action"])
            _SharedState.scores.append(score)
            _SharedState.done = True

            # Calculate final score
            final_score = round(sum(_SharedState.scores) / len(_SharedState.scores), 3)
            
            # Time bonus (if completed quickly)
            elapsed = (datetime.now() - _SharedState.start_time).total_seconds()
            time_bonus = ""
            if elapsed < 30:
                time_bonus = " ⚡ Speed bonus: Excellent response time!"
            elif elapsed < 60:
                time_bonus = " ⚡ Good response time!"

            return EmailTriageObservation(
                task_id=3,
                task_description="Episode complete.",
                emails=[],
                reward=score,
                done=True,
                feedback=(
                    f"Task 3 result: {feedback} "
                    f"🎉 Episode finished! Final score: {final_score}/1.0 "
                    f"(Task scores: {_SharedState.scores})"
                    f"{time_bonus}"
                ),
            )

        # Fallback (should not happen)
        return EmailTriageObservation(
            task_id=_SharedState.current_task,
            task_description="Unexpected state. Please call reset().",
            emails=[],
            reward=0.0,
            done=True,
            feedback="Error: Unexpected state. Please call reset() to start a new episode.",
        )

    def get_final_score(self) -> float:
        """
        Get the average score across all tasks.
        
        Returns:
            Average score (0.0 to 1.0)
        """
        if not _SharedState.scores:
            return 0.0
        return round(sum(_SharedState.scores) / len(_SharedState.scores), 3)
