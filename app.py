import dash
from dash import dcc, html, Input, Output, dash_table, State
import plotly.express as px
import plotly.colors as pcolors
import pdfplumber
import pandas as pd
from datetime import datetime
from io import BytesIO
import base64
import re
from collections import defaultdict

# Initialize the Dash app
external_stylesheets = ['https://fonts.googleapis.com/css2?family=Sour+Gummy&display=swap']
app = dash.Dash(__name__, external_stylesheets = external_stylesheets)

# List of valid test names and units for filtering
VALID_UNITS = ["g/dL", "mg/dL", "mmol/L", "IU/L", "%", "fl", "pg", "pg/mL", "µL", "nmol/L",
               "µIU/mL","mL/min/1.73m2","U/L","thou/mm3"]
VALID_TEST_NAMES = ["Creatinine","GFR Estimated","Glucose Fasting","Cyanocobalamin",
    "Hemoglobin", "RBC", "WBC", "Platelets",  "Cholesterol", "25 Hydroxy","T3, Total","T4, Total",
                "TSH", "Phosphorus", "Sodium", "Potassium", "Chloride","GFR Category G2",
                "Urea","Urea Nitrogen Blood", "Total", "Triglycerides", "HDL Cholesterol",
                "Calculated", "HDL Cholesterol",
"Uric Acid","GGTP","00 RBC Count","HbA1c","MCV","MCH","MCHC","Segmented Neutrophils",
"Lymphocytes","Monocytes","Eosinophils","Basophils","Absolute Leucocyte Count",
"Neutrophils","Lymphocytes","Monocytes","Eosinophils","Basophils","Platelet Count",
"Bilirubin Direct", "Bilirubin Total","Bilirubin Indirect","Total Protein","Albumin","G Ratio"
]

# Function to clean and filter data based on test names and units
def clean_data(data):
    cleaned_data = []
    for entry in data:
        if entry['Test Name'] in VALID_TEST_NAMES and entry['Unit'] in VALID_UNITS:
            cleaned_data.append(entry)
    return cleaned_data

# Function to extract all data from the PDF, including Name and Date
def extract_all_data_from_pdf(content):
    extracted_data = []
    patient_name = None
    collection_date = None
    
    with pdfplumber.open(BytesIO(content)) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text()

        # Extract key-value like structures for test data
        pattern = r'([\w\s]+):?\s+([\d.,]+)\s*([^\s]*)\s*(.*)'
        matches = re.findall(pattern, text)

        # Extract Name and Date using simple patterns
        name_pattern = r'Name\s*:\s*(?:Mr\.|Ms\.)?\s*([A-Za-z]+\s+[A-Za-z]+)'
        date_pattern = r'\b\d{1,2}\/\d{1,2}\/\d{4}\b'

        name_match = re.search(name_pattern, text)
        date_match = re.search(date_pattern, text)

        if name_match:
            patient_name = name_match.group(1)

        if date_match:
            collection_date = date_match.group()

        for match in matches:
            test_name = match[0].strip()
            value = match[1].strip()
            unit = match[2].strip()
            reference_range = match[3].strip()

            # Store raw extracted data, including Name and date
            extracted_data.append({
                'Name': patient_name,
                'Date': collection_date,
                'Test Name': test_name,
                'Value': value,
                'Unit': unit,
                'Reference Range': reference_range
            })

    # Clean the data based on valid test names and units
    return clean_data(extracted_data)

# Layout of the Dash app
app.layout = html.Div([
    html.H1("Health Monitoring System",style={'color':'#007eff',
                                              'font-family': 'Sour Gummy'}),
    
    html.Div([
        dcc.Upload(
            id='upload-data',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select PDF Files')
            ]),
            style={
                'width': '100%',
                'height': '60px',
                'lineHeight': '60px',
                'borderWidth': '1px',
                'borderStyle': 'dashed',
                'borderRadius': '5px',
                'textAlign': 'center',
                'margin': '10px'
            },
            multiple=True  # Allow multiple file uploads
        ),
        html.Div(id='upload-feedback', style={'marginTop': '20px'}),
    ], style={'textAlign': 'center'}),

    # Tabs for switching between views
    dcc.Tabs([
        dcc.Tab(label='Visualize Results', children=[
    # Toggle button for tabular or chart view
    html.Div([
        # Dropdown to select multiple Names for comparison
        html.Div([
            html.Label("Select Patient(s) for Comparison:"),
            dcc.Dropdown(
                id='patient-dropdown',
                options=[],
                placeholder="Select one or more patients",
                multi=True  # Allow multiple selections
            )
        ], style={'width': '50%', 'margin': 'auto', 'padding': '10px'}),
        
        html.Label("View:"),
        dcc.RadioItems(
            id='view-toggle',
            options=[
                {'label': 'Tabular View', 'value': 'table'},
                {'label': 'Charts View', 'value': 'charts'}
            ],
            value='table',  # Default to tabular view
            labelStyle={'display': 'inline-block', 'marginRight': '10px'}
        )
    ], style={'width': '50%', 'margin': 'auto', 'padding': '10px'}),

    html.Div([
        html.Label("Rows per page:"),
        dcc.Input(id="page-size-input", type="number", value=10, min=1, step=1)
    ], style={'margin': '10px 0'}),

    # Export button and download component
    html.Button("Export to CSV", id="export-button", n_clicks=0),
    dcc.Download(id="download-dataframe-csv"),

    # Tabular view
    html.Div(id='tabular-view', children=[
        dash_table.DataTable(
            id='data-table',
            columns=[],  # Will be populated dynamically after upload
            data=[],  # Will be populated dynamically after upload and filter
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '5px',
                'whiteSpace': 'normal',
                'height': 'auto'
            },
            style_header={
                'backgroundColor': 'rgb(230, 230, 230)',
                'fontWeight': 'bold'
            },
            page_size=10,
            filter_action="native",
            sort_action="native"  # Enable sorting feature
        )
    ], style={'display': 'block'}),  # Default to visible
        
    # Charts view
    html.Div(id='charts-view', children=[
        html.Div(id='chart-divs', children=[])  # Will hold separate divs for each test chart
    ], style={'display': 'none'})  # Default to hidden
]),
dcc.Tab(label='Analyze Results', children=[
            html.Div([              
                # Display categorized test results in a table
                dash_table.DataTable(id='analyze-table', 
                style_table={'overflowX': 'auto'},
                page_size=10,
                filter_action="native",
                sort_action="native")
            ])
            ])
    ])
])

# Callback to display test results categorized as Low, Normal, High
@app.callback(
    Output('analyze-table', 'data'),
    Output('analyze-table', 'columns'),
    Input('data-table', 'data')
)
def analyze_test_results(data):       
    # Classify test results based on reference ranges
    for item in data:
        # print(item)
        value = float(item.get('Value'))
        if len(item.get('Reference Range').split('-')) == 2:
            low = float(item.get('Reference Range').split('-')[0].strip())
            high = float(item.get('Reference Range').split('-')[1].strip())
            if value < low:
                item['Category'] = 'Low'
            elif value > high:
                item['Category'] = 'High'
            else:
                item['Category'] = 'Normal'
        else:
            sign = item.get('Reference Range')[0]
            if sign == '<':
                if value > float(item.get('Reference Range')[1:]):
                   item['Category'] = 'High'
                else:
                   item['Category'] = 'Normal'
            else:
                if value < float(item.get('Reference Range')[1:]):
                   item['Category'] = 'Low'
                else:
                   item['Category'] = 'Normal'
    
    # Create table columns
    columns = [
        {'name': 'Name', 'id': 'Name'},
        {'name': 'Date', 'id': 'Date'},
        {'name': 'Test Name', 'id': 'Test Name'},
        {'name': 'Value', 'id': 'Value'},
        {'name': 'Unit', 'id': 'Unit'},
        {'name': 'Reference Range', 'id': 'Reference Range'},
        {'name': 'Category', 'id': 'Category'}     
    ]

    # Return categorized results to the table
    return data, columns

# Callback to handle file upload and extract Names and test data
@app.callback(
    [
        Output('upload-feedback', 'children'),
        Output('data-table', 'data'),
        Output('data-table', 'columns'),
        Output('patient-dropdown', 'options')
    ],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def handle_upload(contents, filenames):
    if contents is None:
        return 'No file uploaded yet.', [], [], []

    files_data = []
    feedback_message = f'Uploaded {len(contents)} file(s): {", ".join(filenames)}'

    for content, filename in zip(contents, filenames):
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)

        # Extract and clean data from the uploaded PDF
        extracted_data = extract_all_data_from_pdf(decoded)
        files_data.extend(extracted_data)

    # Check if data is extracted and cleaned
    if not files_data:
        return feedback_message, [], [], []

    # Restructure data for table display - separate rows for each patient, test, and date
    table_data = []
    for entry in files_data:
        row = {
            'Name': entry['Name'],
            'Date': entry['Date'],
            'Test Name': entry['Test Name'],
            'Value': entry['Value'],
            'Unit': entry['Unit'],
            'Reference Range': entry['Reference Range']
        }
        table_data.append(row)

    # Define table columns
    columns = [
        {'name': 'Name', 'id': 'Name'},
        {'name': 'Date', 'id': 'Date'},
        {'name': 'Test Name', 'id': 'Test Name'},
        {'name': 'Value', 'id': 'Value'},
        {'name': 'Unit', 'id': 'Unit'},
        {'name': 'Reference Range', 'id': 'Reference Range'}
    ]

    # Get unique Names for dropdown options
    unique_names = list(set([entry['Name'] for entry in files_data]))
    
    # Ensure there are valid Names before creating dropdown options
    dropdown_name_options = [{'label': name, 'value': name} for name in unique_names if name]

    return feedback_message, table_data, columns, dropdown_name_options

# Callback to toggle between tabular view and chart view
@app.callback(
    [Output('tabular-view', 'style'), Output('charts-view', 'style')],
    [Input('view-toggle', 'value')]
)
def toggle_view(selected_view):
    if selected_view == 'table':
        return {'display': 'block'}, {'display': 'none'}
    else:
        return {'display': 'none'}, {'display': 'block'}
    
@app.callback(
    Output("data-table", "page_size"),
    Input("page-size-input", "value")
)
def update_page_size(page_size):
    return page_size or 10

# Callback to handle CSV export
@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("export-button", "n_clicks"),
    State("data-table", "data"),
    prevent_initial_call=True
)
def export_to_csv(n_clicks, table_data):
    if n_clicks > 0 and table_data:
        # Convert table data to a DataFrame for export
        df = pd.DataFrame(table_data)
        
        # Convert DataFrame to CSV format and create downloadable CSV
        return dcc.send_data_frame(df.to_csv, "exported_data.csv", index=False)
        
# Callback to update charts for comparison
@app.callback(
    Output('chart-divs', 'children'),
    [Input('patient-dropdown', 'value'),
     Input('data-table', 'data')]
)
def update_charts(selected_names, table_data):
    if not selected_names or not table_data:
        return []

    colors = pcolors.qualitative.Dark2  # You can use other color scales like 'Viridis', 'Cividis', etc.
    color_map = {patient_name: colors[i % len(colors)] for i, patient_name in enumerate(selected_names)}

    # Prepare data for charts
    test_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # Patient -> Test -> Values/Dates
    for row in table_data:
        if row['Name'] in selected_names:
            test_name = row['Test Name']
            
            if row['Value'] != 'N/A':  # Only consider rows with valid values
                test_value = float(row['Value'])
                test_data[row['Name']][test_name]['values'].append(test_value)
                test_data[row['Name']][test_name]['dates'].append(row['Date'])
                test_data[row['Name']][test_name]['range'].append(row['Reference Range'])
                

    # Create charts
    charts = []
    if selected_names:
        first_patient = selected_names[0]  # Take the first selected patient to iterate over test names

        for test_name in test_data[first_patient].keys():  # Iterate over test names for the first patient
            fig = px.line()
            
            for patient_name in selected_names:
                if test_name in test_data[patient_name]:
                    # Sort dates and values by dates in ascending order
                    dates = [datetime.strptime(date, '%d/%m/%Y') for date in test_data[patient_name][test_name]['dates']]
                    sorted_data = sorted(zip(dates, test_data[patient_name][test_name]['values']), key=lambda x: x[0], reverse=True)
                    sorted_dates, sorted_values = zip(*sorted_data)
                    ref = test_data[patient_name][test_name]['range'][0].split(' - ')
                    if len(ref) == 2:
                        low = test_data[patient_name][test_name]['range'][0].split(' - ')[0]
                        high = test_data[patient_name][test_name]['range'][0].split(' - ')[1]
                    else:
                        low = test_data[patient_name][test_name]['range'][0].split(' - ')[0]
                        high = float(test_data[patient_name][test_name]['range'][0].split(' - ')[0][1:])

                    # Add sorted scatter plot to the figure
                    fig.add_scatter(
                        x=sorted_dates,
                        y=sorted_values,
                        mode='lines+markers',
                        name=patient_name,
                        line=dict(color=color_map[patient_name])
                    )

                    if low is not None:
                        fig.add_shape(type="line",
                                  x0=min(sorted_dates), x1=max(sorted_dates),
                                  y0=low, y1=low,
                                  line=dict(color=color_map[patient_name], dash="dash"),  # Low reference line
                                  name="Low Reference")
                    if high is not None:
                        fig.add_shape(type="line",
                                    x0=min(sorted_dates), x1=max(sorted_dates),
                                    y0=high, y1=high,
                                    line=dict(color=color_map[patient_name], dash="dash"),  # High reference line
                                    name="High Reference")
                    
            fig.update_layout(title=f'{test_name}', xaxis_title='Date', yaxis_title=test_name)
            charts.append(html.Div([
                dcc.Graph(figure=fig)
            ], style={'margin': '20px 0'}))

    return charts

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port=8050)
