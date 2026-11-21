import re
from fastapi.testclient import TestClient
from app.main import app
from app.api_docs import OPERATIONS


def test_every_api_operation_and_parameter_has_korean_explanation():
    schema=TestClient(app).get('/openapi.json').json()
    assert schema['info']['title']=='트립버짓 여행 추천 API'
    assert set(schema['paths'])==set(OPERATIONS)
    for methods in schema['paths'].values():
        for operation in methods.values():
            assert re.search('[가-힣]',operation['summary'])
            assert re.search('[가-힣]',operation['description'])
            assert all(re.search('[가-힣]',tag) for tag in operation['tags'])
            for parameter in operation.get('parameters',[]):
                assert re.search('[가-힣]',parameter['description'])
                assert re.search('[가-힣]',parameter['schema']['title'])
            for response in operation['responses'].values():
                assert re.search('[가-힣]',response['description'])


def test_request_schema_explanations_are_korean_and_contract_is_preserved():
    schema=app.openapi()
    for definition in schema['components']['schemas'].values():
        assert re.search('[가-힣]',definition['title'])
        for field in definition.get('properties',{}).values():
            assert re.search('[가-힣]',field['title'])
            assert re.search('[가-힣]',field['description'])
    request=schema['components']['schemas']['ItineraryRequest']
    assert 'cityName' in request['properties'] and 'budget' in request['required']
    assert request['properties']['budget']['maximum']==1000000000
    assert request['properties']['days']['maximum']==14
    validation=schema['paths']['/api/generate-itinerary']['post']['responses']['422']
    assert validation['content']['application/json']['schema']['$ref'].endswith('/HTTPValidationError')


def test_docs_page_and_health_response_remain_available():
    client=TestClient(app)
    response=client.get('/docs')
    assert response.status_code==200
    assert '트립버짓 여행 추천 API' in response.text
    assert client.get('/api/health').json()['status']=='ok'
