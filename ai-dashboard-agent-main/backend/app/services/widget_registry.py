WIDGET_REGISTRY = {
    "sales_chart": {
        "widget_id": "sales_chart",
        "title": "Sales Chart",
        "supported_intents": ["sales_analysis"],
        "metrics": ["sales"],
        "visibility": "show_on_sales_query",
    },
    "service_count_chart": {
        "widget_id": "service_count_chart",
        "title": "Service Count Chart",
        "supported_intents": ["service_analysis"],
        "metrics": ["service_count"],
        "visibility": "show_on_service_query",
    },
    "inventory_table": {
        "widget_id": "inventory_table",
        "title": "Inventory Table",
        "supported_intents": ["inventory_analysis"],
        "metrics": ["stock"],
        "visibility": "show_on_inventory_query",
    },
    "tenant_comparison_chart": {
        "widget_id": "tenant_comparison_chart",
        "title": "Tenant Comparison Chart",
        "supported_intents": ["tenant_comparison"],
        "metrics": ["sales", "service_count"],
        "visibility": "admin_only",
    },
}


def get_all_widget_ids() -> list[str]:
    return list(WIDGET_REGISTRY.keys())


def get_widgets_for_intent(intent: str) -> list[str]:
    return [
        widget_id
        for widget_id, widget in WIDGET_REGISTRY.items()
        if intent in widget["supported_intents"]
    ]


def get_hidden_widgets(visible_widgets: list[str]) -> list[str]:
    return [
        widget_id
        for widget_id in get_all_widget_ids()
        if widget_id not in visible_widgets
    ]
