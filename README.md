# Bus Ticket Analytics & Intelligence Dashboard

## Stack
Python, Pandas, Streamlit, Plotly.

## Run on Windows
1. Extract the ZIP.
2. Open the folder in VS Code.
3. Open Terminal:
   ```powershell
   python -m venv .venv
   .venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   streamlit run app/app.py
   ```
4. Streamlit opens the dashboard in your browser.
5. The provided dataset loads automatically. You can also upload another `.xlsx` workbook using the sidebar.

## Features
- KPI cards for passengers, ticket transactions, collected/uncollected amount and waybills.
- Passenger demand by hour.
- Top boarding stops and destinations.
- Route ranking and origin-destination matrix.
- Automatic descriptive insights.
- Data quality flags.
- Stop/time filters and filtered CSV download.

## Important data interpretation
- The provided workbook has one day of data, dated 20 October 2026.
- Ticket Number repeats across waybills; transaction count is row count.
- One missing destination and five zero-passenger rows are retained and flagged.
- Rows with both collected and uncollected amounts positive are flagged for review, not classified as fraud.
- Uncollected amount is not money received. Confirm its business meaning with the organizers.
- One day cannot support reliable weekly/monthly trend claims or forecasting.
