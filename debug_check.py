from scheduler import get_sheet_client, fetch_new_responses
import traceback

try:
    client = get_sheet_client()
    new_rows, last_row = fetch_new_responses(client)
    print('ok', len(new_rows), last_row)
except Exception as e:
    print('EXC:', repr(e))
    traceback.print_exc()
