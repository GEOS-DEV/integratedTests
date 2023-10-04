import os
import pathlib
import dash    # type: ignore[import]
from dash import dcc, html, dash_table, no_update
from dash.dependencies import Input, Output, State    # type: ignore[import]
import dash_bootstrap_components as dbc
import themes
from flask import send_from_directory
import plotly.graph_objs as go
import numpy as np
import pandas as pd
from collections import Counter


test_status_colors = {
    'FILTERED': 'grey',
    'NOT BUILT': 'grey',
    'NOT RUN': 'blue',
    'BATCHED': 'brown',
    'INPROGRESS': 'cyan',
    'PASSED': 'green',
    'EXPECTEDFAIL': 'green',
    'TIMEOUT': 'yellow',
    'SKIPPED': 'orange',
    'FAIL RUN': 'magenta',
    'UNEXPECTEDPASS': 'red',
    'FAIL RUN (OPTIONAL STEP)': 'pink',
    'FAIL CHECK': 'red',
    'FAIL CHECK (MINOR)': 'pink',
}



def parse_ats_txt_report(fname):
    if not os.path.isfile(fname):
        return {'TestCase': ['ATS'],
                'Status': ['Report not found'],
                'TestStep': ['ats'],
                'Elapsed': [0.0]}

    report_header = []
    report_table = []
    report_section = 0
    line_break = False
    with open(fname, 'r') as f:
        for line in f:
            if (report_section == 0):
                if 'Status' in line:
                    report_section += 1
                    report_header = [x.strip() for x in line.split(' : ')]
            else:
                if '--' in line:
                    continue
                else:
                    tmp = [x.strip() for x in line.split(' : ')]
                    if tmp[0]:
                        report_table.append(tmp)

    # Fallback in case file parsing failed
    if not report_header:
        return {'TestCase': ['ATS'],
                'Status': ['Report parsing failed'],
                'TestStep': ['ats'],
                'Elapsed': [0.0]}

    # Format the table
    report = {}
    for ii, k in enumerate(report_header):
        report[k] = [x[ii] for x in report_table]

    return report


def convert_dict_to_datatable(x, column_map=[], row_key='TestCase'):
    table = []
    for ii, ka in enumerate(x[row_key]):
        # Parse the name and rank information
        case_name = ka
        case_ranks = 1
        jj = ka.rfind('_')
        if jj > 0:
            case_name = ka[:jj]
            case_ranks = ka[jj+1:]

            if '-' in case_ranks:
                tmp = 1
                for y in case_ranks.split('-'):
                    tmp *= int(y)
                case_ranks = tmp
            else:
                case_ranks = int(case_ranks)

        case = {'Name': case_name, 'Ranks': str(case_ranks), 'id': case_name}
        for kb, kc in column_map:
            case[kc] = x[kb][ii]
        table.append(case)
    return table


class GEOSTestingDashboard():
    """
    DASH GUI base class for STRIVE

    Attributes:
        main_buttons (dict): An object to hold the control buttons in the gui
    """

    def __init__(self, update_interval=10000):
        """
        Main Orion gui initialization
        """
        self.name = "GUI Base"
        self.app = None
        self.update_interval = update_interval
        self.banner_url = {
            'General Documentation': {
                'url': 'https://geosx-geosx.readthedocs-hosted.com/en/latest/index.html'
            },
            'Testing Documentation': {
                'url': 'https://geosx-geosx.readthedocs-hosted.com/en/latest/docs/sphinx/developerGuide/Contributing/IntegratedTests.html'
            },
            'GEOS': {
                'url': 'https://github.com/GEOS-DEV/GEOS'
            }
        }
        self.banner_header = 'GEOS'
        self.banner_subheader = 'Integrated Testing Dashboard'
        self.title_url = self.banner_url['GEOS']['url']
        self.last_tab = ''
        self.collapsable_depth = 1
        self.config_states = []
        self.config_state_map = {}
        self.tab_user_map = []
        self.config_offset = 0
        self.figure_ids = []
        self.figure_methods = []
        self.figure_handles = []
        self.figure_widget_inputs = {}
        self.figure_widget_inputs_order = []
        self.user_type = ''
        self.plot_fontstyle = {'color': 'white', 'size': 12}

        self.ats_report_file = '~/GEOS/build-quartz-gcc-12-release/integratedTests/TestResults/test_results.txt'
        self.ats_report_last_checked = 0
        self._first_render = True
        self._layout = None

    def run(self, debug=True, port=8050):
        if self.app is not None:
            self.app.run_server(debug=debug, port=port, host='127.0.0.1')

    def serve_interface(self):
        self._first_render = True
        if self._layout is not None:
            return self._layout

        self._layout = html.Div(
            id="interface-container",
            children=[
                html.Link(rel='stylesheet', href=themes.base_style),
                html.Link(rel='stylesheet', href=themes.custom_style),
                html.Link(rel='stylesheet', href=themes.fonts_style),
                self.build_navigation_bar(),
                dcc.Interval(
                    id="interval-component",
                    interval=self.update_interval,
                    disabled=False,
                ),
                html.Div(
                    id="app-container",
                    children=[
                        self.build_tabs(),
                        html.Div(id="app-content"),
                    ],
                ),
                dcc.Store(id="value-setter-store", data={}),
                dcc.Store(id="n-interval-stage", data=50),
                dcc.Store(id="current-test-name", data=''),
                self.build_help_popup(),
            ],
        )

        return self._layout

    def build_interface(self):
        """
        Build the primary interface
        """
        self.app = dash.Dash(self.name,
                             meta_tags=[{
                                 "name": "viewport",
                                 "content": "width=device-width, initial-scale=1"
                             }],
                             external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.app.title = self.name
        self.app.config["suppress_callback_exceptions"] = True
        self.app.css.config.serve_locally = True
        self.app.scripts.config.serve_locally = True
        self.app.layout = self.serve_interface

        @self.app.server.route('/theme/<path:path>')
        def static_file(path):
            return send_from_directory(themes.pwd, path)

    def generate_section_banner(self, title):
        return html.Div(className="section-banner", children=title)

    def add_collapsible_div(self, name, child_items):
        """
        Add a collapsible element to a group

        Args:
            name (str): The name of the element that will be placed in the corresponding button
            child_items (list): A list of the collapsible div children

        Returns:
            html.Div: The collapsible div
        """
        child_id = f'collapse_div_{name}'
        card_id = f'collapse_card_{name}'
        button_id = f'collapse_button_{name}'
        child_button = dbc.Button(name, id=button_id, color="primary", n_clicks=0, className="widget-button")
        card = dbc.Card(dbc.ListGroup(child_items, flush=True), id=card_id, className="card")
        child_div = dbc.Collapse(
            card,
            id=child_id,
            is_open=True,
        )
        collapsable_div = html.Div(children=[child_button, child_div])

        # Register a callback to allow for collapsing the div
        @self.app.callback(
            Output(child_id, "is_open"),
            [Input(button_id, "n_clicks")],
            [State(child_id, "is_open")],
        )
        def toggle_collapse(n, is_open):
            if n:
                return not is_open
            return is_open

        return collapsable_div

    def build_navigation_bar(self):
        """
        Build the application navigation bar

        Returns:
            html.Div: The navigation bar group
        """
        titlebar = html.A(
            dbc.Row(
                [
                    # dbc.Col(html.Img(src=self.logo, height="30px")),
                    dbc.Col(dbc.NavbarBrand(self.banner_header, className="ms-2")),
                    dbc.Col(dbc.NavbarBrand(self.banner_subheader, className="ms-2")),
                ],
                align="center",
                className="g-0",
            ),
            href=self.title_url,
            style={"textDecoration": "none"},
        )

        # Setup main menu
        dropdown_items = [
            dbc.DropdownMenuItem("Help", id="learn-more-button", n_clicks=0),
        ]

        for k, v in self.banner_url.items():
            url = v.get('url', None)
            dropdown_items.append(html.A(dbc.DropdownMenuItem(k), href=url))

        dropdown = dbc.DropdownMenu(children=dropdown_items,
                                    menu_variant="dark",
                                    in_navbar=True,
                                    label="Menu",
                                    color="secondary",
                                    align_end=True)

        navbar = dbc.Navbar(
            dbc.Container([titlebar, dropdown], fluid=True),
            color="dark",
            dark=True,
        )

        return navbar

    def build_tabs(self):
        """
        Build the tab group

        Returns:
            html.Div: The tab group
        """
        pages = [self.build_test_overview_page(),
                 self.build_test_config_page()]

        tabs = html.Div(
            id="tabs",
            className="tabs",
            children=[dcc.Tabs(
                id="app-tabs",
                value=pages[0].value,
                className="custom-tabs",
                children=pages,
            )],
        )

        return tabs

    def build_test_overview_page(self):
        table = dash_table.DataTable(
            id='overview_table',
            page_action='none',
            sort_action='native',
            style_table={
                'height': '300px',
                # 'width': '90vw',
                'overflowY': 'auto'
            },
            style_cell={
                'backgroundColor': '#1e2130',
                'minWidth': 95,
                'maxWidth': 95,
                'width': 95,
                'height': 'auto',
                'whiteSpace': 'normal'
            },
            style_header={
                'backgroundColor': '#242633',
                'minWidth': 95,
                'maxWidth': 95,
                'width': 95,
                'fontWeight': 'bold'
            })
        table_div = html.Div(table, style={'border': '1px solid'})

        status_pie_chart = dcc.Graph(id='status_pie_chart', figure=self.build_dummy_figure())
        test_details = self.build_test_detail_group()
        overview_div = html.Div(
            id=f'test_overview',
            children=[status_pie_chart, table_div, test_details],
            className="figure-page",
        )

        page = dcc.Tab(id=f"STRIVE-tab-configuration",
                       label="Overview",
                       value='overview',
                       children=overview_div,
                       className="custom-tab",
                       selected_className="custom-tab--selected")

        # Build the pie chart updater
        @self.app.callback([Output("overview_table", "data"), Output("overview_table", "columns"), Output('status_pie_chart', 'figure')], Input('interval-component', 'n_intervals'))
        def render_test_overview(*xargs):
            self.ats_report_file = os.path.expanduser(self.ats_report_file)
            report_time = os.stat(self.ats_report_file).st_mtime
            if (report_time < self.ats_report_last_checked + 1.0) and self._first_render:
                # print('skipping')
                return no_update, no_update, no_update

            self.ats_report_last_checked = report_time
            report = parse_ats_txt_report(self.ats_report_file)

            # Load the test report
            column_map = [['Status', 'Status'], ['TestStep', 'Step'], ['Elapsed', 'Time']]
            td = convert_dict_to_datatable(report, column_map=column_map)
            columns = [{"name": x, "id": x} for x in td[0].keys()]

            # Render the status figure
            status_count = Counter(report['Status'])
            fig = go.Figure(data=[go.Pie(labels=list(status_count.keys()), values=list(status_count.values()))])
            fig.update_layout(clickmode='event+select',
                      showlegend=True,
                      margin=dict(l=20, r=20, t=10, b=90),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      font_color="white",
                      title_font_color="white",
                      xaxis_title_font_color="white",
                      yaxis_title_font_color="white",
                      font_family="Open Sans",
                      title_font_family="Open Sans",
                      xaxis_title_font_family="Open Sans",
                      yaxis_title_font_family="Open Sans",
                      font_size=14,
                      title_font_size=14,
                      xaxis_title_font_size=14,
                      yaxis_title_font_size=14,
                      autosize=True)

            self._first_render = False
            return td, columns, fig

        return page

    def build_dummy_figure(self):
        """
        Build a dummy figure
        """
        fig = go.Figure()
        
        axis_def = {
            'mirror': True,
            'ticks': 'outside',
            'showline': False,
            'zeroline': False,
            'showgrid': False,
            'tickcolor': 'rgba(0,0,0,0)'
        }
        fig.update_layout(xaxis_title="",
                          yaxis_title="",
                          clickmode='event+select',
                          showlegend=True,
                          margin=dict(l=20, r=20, t=10, b=90),
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)",
                          font_color="rgba(0,0,0,0)",
                          title_font_color="rgba(0,0,0,0)",
                          xaxis_title_font_color="rgba(0,0,0,0)",
                          yaxis_title_font_color="rgba(0,0,0,0)",
                          autosize=True,
                          xaxis=axis_def,
                          yaxis=axis_def)
        return fig

    def build_test_detail_group(self):
        """
        Build the test detail group
        """
        detail_banner = html.Div(id="test-detail-banner", className="section-banner", children="")

        # Curve check group
        curve_options = ['(none)']
        curve_dropdown = html.Div(children=[dcc.Dropdown(options=curve_options, value=curve_options[0], id='curve-select-dropdown')], className='widget-dropdown')
        curve_tolerance_str = html.Div('', id='curve-tolerance-str')
        curve_status_str = html.Div('', id='curve-status-str')
        curve_items = [
            html.Div(children=['Curve:', curve_dropdown], className="widget"),
            html.Div(children=['Tolerance:', curve_tolerance_str], className="widget"),
            html.Div(children=['Status:', curve_status_str], className="widget"),
            dcc.Graph(id='curve_figure', figure=self.build_dummy_figure()),
            ]
        curve_div = html.Div(self.add_collapsible_div('Curve Check', curve_items), id='curve_check_visibility')

        # Restart check group
        restart_absolute_tolerance_str = html.Div('0.0', id='restart-absolute-tolerance-str')
        restart_relative_tolerance_str = html.Div('0.0', id='restart-relative-tolerance-str')
        restart_status_str = html.Div('Passed', id='restart-status-str')
        restart_log = dcc.Textarea(
            id='restart-log',
            value='Textarea content initialized\nwith multiple lines of text',
            style={'width': '100%', 'height': 300, 'background-color': 'black', 'color': 'white'},
            readOnly=True,
        )
        restart_items = html.Div([
            html.Div(children=['Absolute tolerance:', restart_absolute_tolerance_str], className="widget"),
            html.Div(children=['Relative tolerance:', restart_relative_tolerance_str], className="widget"),
            html.Div(children=['Status:', restart_status_str], className="widget"),
            html.Div('Restart Check Log'),
            restart_log,
            ])
        restart_div = html.Div(self.add_collapsible_div('Restart Check', restart_items), id='restart_check_visibility')

        # Run log group
        run_log = dcc.Textarea(
            id='run-log',
            value='Textarea content initialized\nwith multiple lines of text',
            style={'width': '100%', 'height': 300, 'background-color': 'black', 'color': 'white'},
            readOnly=True,
        )
        run_err = dcc.Textarea(
            id='run-err',
            value='Textarea content initialized\nwith multiple lines of text',
            style={'width': '100%', 'height': 400, 'background-color': 'black', 'color': 'white'},
            readOnly=True,
        )
        run_items = html.Div([
            html.Div('Standard Output:'),
            run_log,
            html.Div('Standard Error:'),
            run_err,
            ])
        run_div = self.add_collapsible_div('Logs', run_items)

        # Test details callback
        inputs = [
            Input('overview_table', 'active_cell'),
            State("overview_table", "data")
        ]
        outputs = [
            Output('test-detail-banner', 'children'),
            Output('curve_check_visibility', 'hidden'),
            Output('curve-select-dropdown', 'options'),
            Output('curve-select-dropdown', 'value'),
            Output('current-test-name', 'data'),
            Output('restart_check_visibility', 'hidden'),
            Output('restart-absolute-tolerance-str', 'children'),
            Output('restart-relative-tolerance-str', 'children'),
            Output('restart-log', 'value'),
            Output('run-log', 'value'),
            Output('run-err', 'value')]
        @self.app.callback(outputs, inputs)
        def render_test_details(active_cell, table_data):
            if not active_cell:
                results = [
                    "Test: None Selected",
                    True,
                    no_update,
                    no_update,
                    no_update,
                    True,
                    no_update,
                    no_update,
                    no_update,
                    no_update,
                    no_update
                ]
                return results

            row_number = active_cell.get('row', 0)
            test_id = active_cell.get('row_id', 'None')
            test_details = table_data[row_number]
            test_status = test_details['Status']
            test_color = test_status_colors[test_status]
            status_text = html.Div(f'Test: {test_id}, Status: {test_status}', style={'color': test_color})
            dropdown_values = ['option_a', 'option_b', 'option_c']

            has_curve_check = True
            has_restart_check = True

            results = [
                status_text,
                not has_curve_check,
                dropdown_values,
                dropdown_values[0],
                test_id,
                not has_restart_check,
                str(np.random.randn()),
                str(np.random.randn()),
                'The restart check log',
                'The run log',
                'The run errors',
            ]

            return results

        # Curve check figure callback
        inputs = [Input('current-test-name', 'data'), Input('curve-select-dropdown', 'value')]
        outputs = [Output('curve_figure', 'figure'), Output('curve-tolerance-str', 'children'), Output('curve-status-str', 'children')]
        @self.app.callback(outputs, inputs)
        def render_curve_check_figure(current_test, current_curve):
            results = [self.render_curvecheck_figure(current_test, current_curve),
                       str(np.random.randn()),
                       html.Div('Passed', style={'color': 'green'})]
            return results

        return html.Div([detail_banner, curve_div, restart_div, run_div])

    def render_curvecheck_figure(self, current_test, current_curve):
        fig = go.Figure()
        x = np.linspace(0, 1, 100)
        y = x + np.random.randn(100)
        fig.add_trace(go.Scatter(x=x, y=y))

        # Setup axes
        axis_def = {
            'mirror': True,
            'ticks': 'outside',
            'showline': True,
            'zeroline': False,
            'showgrid': False,
            'tickcolor': 'white'
        }
        fig.update_layout(xaxis_title="X",
                          yaxis_title="Y",
                          clickmode='event+select',
                          showlegend=True,
                          margin=dict(l=20, r=20, t=10, b=90),
                          paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white",
                          title_font_color="white",
                          xaxis_title_font_color="white",
                          yaxis_title_font_color="white",
                          autosize=True,
                          xaxis=axis_def,
                          yaxis=axis_def)
        return fig

    def build_test_config_page(self):
        div = html.Div(
            id=f'test_config',
            children=html.P('Some other text'),
            className="figure-page",
        )

        page = dcc.Tab(id=f"STRIVE-tab-geos",
                       label="Configuration",
                       value='configuration',
                       children=div,
                       className="custom-tab",
                       selected_className="custom-tab--selected")
        return page

    def build_help_popup(self):
        popup = html.Div(
            id="markdown",
            className="help-popup",
            children=(html.Div(
                id="markdown-container",
                className="markdown-container",
                children=[
                    html.Div(
                        className="close-container",
                        children=html.Button(
                            "Close",
                            id="markdown_close",
                            n_clicks=0,
                            className="closeButton",
                        ),
                    ),
                    html.Div(
                        className="markdown-text",
                        children=dcc.Markdown(children=("""
                            Help Text

                        """)),
                    ),
                ],
            )),
        )

        @self.app.callback(
            Output("markdown", "style"),
            [Input("learn-more-button", "n_clicks"),
             Input("markdown_close", "n_clicks")],
        )
        def update_click_output(button_click, close_click):
            ctx = dash.callback_context
            if ctx.triggered:
                prop_id = ctx.triggered[0]["prop_id"].split(".")[0]
                if prop_id == "learn-more-button":
                    return {"display": "block"}

            return {"display": "none"}

        return popup


def main():
    gui = GEOSTestingDashboard()
    gui.build_interface()
    gui.run()


if __name__ == '__main__':
    main()
