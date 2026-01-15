from typing import Optional, List, Dict
from pyairtable import Api, Table
from config import Config


class AirtableService:
    """Service for interacting with Airtable for portfolio and pipeline data."""

    def __init__(self):
        self.api = Api(Config.AIRTABLE_API_KEY) if Config.AIRTABLE_API_KEY else None
        self.base_id = Config.AIRTABLE_BASE_ID

    def _get_table(self, table_name: str) -> Optional[Table]:
        """Get a table instance."""
        if not self.api or not self.base_id:
            return None
        return self.api.table(self.base_id, table_name)

    def get_portfolio_company(self, company_name: str) -> Optional[Dict]:
        """Get portfolio company data by name."""
        table = self._get_table("Portfolio Companies")
        if not table:
            return None

        try:
            # Search for company by name (case-insensitive)
            records = table.all(formula=f"LOWER({{Name}}) = LOWER('{company_name}')")
            if records:
                record = records[0]
                return {
                    "id": record["id"],
                    "name": record["fields"].get("Name"),
                    "stage": record["fields"].get("Stage"),
                    "valuation": record["fields"].get("Last Valuation"),
                    "metrics": record["fields"].get("Key Metrics"),
                    "last_board": record["fields"].get("Last Board Meeting"),
                    "sector": record["fields"].get("Sector"),
                    "lead_partner": record["fields"].get("Lead Partner"),
                    "investment_date": record["fields"].get("Investment Date"),
                    "notes": record["fields"].get("Notes"),
                }
            return None
        except Exception as e:
            print(f"Error fetching company from Airtable: {e}")
            return None

    def get_all_portfolio_companies(self) -> List[Dict]:
        """Get all portfolio companies."""
        table = self._get_table("Portfolio Companies")
        if not table:
            return []

        try:
            records = table.all()
            return [
                {
                    "id": record["id"],
                    "name": record["fields"].get("Name"),
                    "stage": record["fields"].get("Stage"),
                    "sector": record["fields"].get("Sector"),
                    "lead_partner": record["fields"].get("Lead Partner"),
                }
                for record in records
            ]
        except Exception as e:
            print(f"Error fetching companies from Airtable: {e}")
            return []

    def get_pipeline_deals(self, status: str = None) -> List[Dict]:
        """Get pipeline deals, optionally filtered by status."""
        table = self._get_table("Pipeline")
        if not table:
            return []

        try:
            if status:
                records = table.all(formula=f"{{Status}} = '{status}'")
            else:
                records = table.all()

            return [
                {
                    "id": record["id"],
                    "company": record["fields"].get("Company Name"),
                    "status": record["fields"].get("Status"),
                    "sector": record["fields"].get("Sector"),
                    "owner": record["fields"].get("Deal Owner"),
                    "stage": record["fields"].get("Deal Stage"),
                    "notes": record["fields"].get("Notes"),
                    "next_steps": record["fields"].get("Next Steps"),
                }
                for record in records
            ]
        except Exception as e:
            print(f"Error fetching pipeline from Airtable: {e}")
            return []

    def update_company_notes(self, company_name: str, notes: str) -> bool:
        """Update notes for a portfolio company."""
        table = self._get_table("Portfolio Companies")
        if not table:
            return False

        try:
            records = table.all(formula=f"LOWER({{Name}}) = LOWER('{company_name}')")
            if records:
                record_id = records[0]["id"]
                existing_notes = records[0]["fields"].get("Notes", "")
                updated_notes = f"{existing_notes}\n\n---\n{notes}" if existing_notes else notes
                table.update(record_id, {"Notes": updated_notes})
                return True
            return False
        except Exception as e:
            print(f"Error updating company notes: {e}")
            return False

    def add_agenda_item_to_airtable(self, category: str, item: str, submitted_by: str) -> bool:
        """Add an agenda item to an Airtable tracking table."""
        table = self._get_table("Meeting Agenda Items")
        if not table:
            return False

        try:
            table.create({
                "Category": category,
                "Item": item,
                "Submitted By": submitted_by,
                "Status": "Pending",
            })
            return True
        except Exception as e:
            print(f"Error adding agenda item to Airtable: {e}")
            return False

    def get_company_slack_channel(self, company_name: str) -> Optional[str]:
        """Get the Slack channel name for a portfolio company."""
        company = self.get_portfolio_company(company_name)
        if company:
            # Try to get from Airtable, or construct from naming convention
            channel = company.get("slack_channel")
            if channel:
                return channel
            # Fall back to convention: portfolio-companyname
            return f"{Config.PORTFOLIO_CHANNEL_PREFIX}{company_name.lower().replace(' ', '-')}"
        return None

    def is_configured(self) -> bool:
        """Check if Airtable is properly configured."""
        return bool(self.api and self.base_id)
