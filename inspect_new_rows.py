from scheduler import get_sheet_client, fetch_new_responses
import pprint

client = get_sheet_client()
new_rows, last_row = fetch_new_responses(client)
print('last_processed_row:', last_row)
print('num_new_rows:', len(new_rows))
for i, row in enumerate(new_rows, start=1):
    sheet_row = last_row + i
    print('\n--- sheet_row:', sheet_row, '---')
    pprint.pp(row)
