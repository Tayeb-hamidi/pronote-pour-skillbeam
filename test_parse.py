import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../services/api-gateway/app')))

try:
    with open('../test.xml', 'r') as f:
        xml_content = f.read()
    
    from main import _parse_pronote_xml
    parsed, by_type = _parse_pronote_xml(xml_content)
    print("Parsed Items:", len(parsed))
    for item in parsed:
        print(item['item_type'], item['prompt'][:50])
    print("By Type:", by_type)
except Exception as e:
    import traceback
    traceback.print_exc()
