"""Korean OpenAPI documentation without changing request/response contracts."""
from fastapi.openapi.utils import get_openapi

FIELD_DOCS = {
    'departureAirport':('출발 공항', '대한민국 출발 공항의 IATA 세 글자 코드를 입력합니다. 공항 선택 API 결과를 사용합니다.'),
    'arrivalAirport':('도착 공항', '선택한 여행지와 같은 국가에 있는 공항의 IATA 세 글자 코드를 입력합니다.'),
    'regionName':('행정구역 표시 이름', '여행지가 속한 시·도와 시·군 등의 행정구역명입니다.'),
    'regionId':('국내 지역 식별자', '국내·해외 지역 추천 응답의 regionId를 저장·복원합니다. 국내는 등록 행정지역, 해외는 선택 도시의 경계를 확인해 명소를 조회합니다.'),
    'destinationType':('여행지 단위', 'region은 국내 행정지역 또는 해외 도시 지역입니다. 해당 지역의 명소는 일정 생성 단계에서 조회합니다.'),
    'refresh':('일정 다시 생성', '선택 항목입니다. true이면 저장된 동선 대신 새 일정을 생성합니다. 진행 중인 동일 요청은 합치며 실제 API 사용량이 발생할 수 있습니다.'),
    'englishName':('영어 지명', '공급자가 제공한 영어 지명입니다. 등록 지명 사전 대조에 사용할 수 있으며 자동 번역에는 사용하지 않습니다. 최대 200자입니다.'),
    'names':('지도 지명 목록', '한국어 이름이 없는 영어 지명을 최대 24개 전달합니다. 이름당 최대 128자입니다. 로컬 LibreTranslate와 저장된 번역을 사용합니다.'),
    'budget':('전체 여행 예산', '전체 인원·전체 기간의 총예산입니다. 원 단위 정수로 입력합니다. 예: 500만원은 5000000. 만원 같은 문자 단위는 프론트엔드에서만 변환합니다.'),
    'cityName':('여행지 식별 이름', '도시 목록이나 여행지 조회 응답의 cityName 값을 그대로 입력합니다. displayName과 다를 수 있습니다.'),
    'category':('여행 지역', 'all: 전체, domestic: 국내, international: 해외입니다. 이 항목에 표시된 허용값 중 하나를 입력합니다.'),
    'days':('여행 기간', '전체 여행 일수입니다. 1~14일이며 3은 2박 3일을 뜻합니다.'),
    'people':('성인 여행 인원', '전체 성인 인원입니다. 1~10명이며 숙소는 기본 2인 1실로 계산합니다.'),
    'origin':('출발 지역', '지역 코드를 입력합니다. seoul: 서울, incheon: 인천, gyeonggi: 경기, gangwon: 강원, busan: 부산, daegu: 대구, daejeon: 대전, gwangju: 광주, ulsan: 울산, sejong: 세종, chungbuk: 충북, chungnam: 충남, jeonbuk: 전북, jeonnam: 전남, gyeongbuk: 경북, gyeongnam: 경남, jeju: 제주.'),
    'themes':('여행 카테고리 복수 선택', 'relaxation(휴양), sightseeing(관광), food(맛집), activity(액티비티), shopping(쇼핑), nature(자연/트레킹), photography(감성사진)을 배열로 전달합니다. 최대 7개이며 중복은 한 번만 반영합니다. 빈 배열은 기본 경비만 계산합니다. 랜덤 GET은 themes=food&themes=shopping처럼 반복 전달하며 themes=는 선택 없음입니다. 식비·쇼핑·체험 등 계획용 예산과 AI 일정에 반영합니다. 생략 시 기존 theme을 사용합니다.'),
    'theme':('여행 카테고리', 'relaxation: 휴양, sightseeing: 관광, food: 맛집, activity: 액티비티, shopping: 쇼핑, nature: 자연/트레킹, photography: 감성사진입니다. AI 일정의 장소 선택·활동·식사 제안에 선호를 반영합니다. 생략 시 관광입니다.'),
    'style':('이전 경비 계산 방식', '기존 API·백업 호환용입니다. 새 화면에서는 standard를 사용하며 여행 카테고리는 themes로 복수 선택합니다.'),
    'departureDate':('출발일', '선택 항목입니다. 날짜는 2026-12-01처럼 연-월-일 형식으로 입력합니다. 생략하면 숙박의 주말·성수기 가산을 반영하지 않습니다.'),
    'transportPerPerson':('확인한 1인 왕복 교통비', '선택 항목입니다. 원 단위 정수로 0~20000000을 입력합니다. 생략하면 자동 추정하며 0은 무료를 뜻합니다.'),
    'hotelPerRoomNight':('확인한 객실당 1박 숙박비', '선택 항목입니다. 원 단위 정수로 0~5000000을 입력합니다. 생략하면 자동 추정하며 0은 무료를 뜻합니다.'),
    'destinationNames':('비교할 여행지 이름 목록', '선택 항목입니다. 기존 목록 또는 최근 검색 결과의 cityName을 최대 200개 입력합니다. 생략하면 기본 목록을 비교합니다. 서버 재시작 등으로 조회 결과가 만료되면 다시 검색해야 합니다.'),
    'lat':('위도', '여행지 위도입니다. -90~90 범위의 숫자입니다.'),
    'lng':('경도', '여행지 경도입니다. -180~180 범위의 숫자입니다.'),
    'countryCode':('국가 코드', '두 글자 소문자 국가 코드를 입력합니다. 예: kr은 대한민국, jp는 일본, fr은 프랑스입니다. 여행지 추첨·비교에서 생략하면 국가를 제한하지 않습니다. 지정하면 해당 국가만 조회하며 국내·해외 조건도 일치해야 합니다.'),
    'q':('여행지 검색어', '2~100자의 도시명이나 관광지 이름을 입력합니다. 공백을 제외한 검색어도 두 글자 이상이어야 합니다.'),
    'detail':('오류 상세', '요청을 처리하지 못한 이유 또는 입력값 검증 오류 목록입니다.'),
    'loc':('오류 발생 위치', '오류가 발생한 요청 영역과 필드 이름을 순서대로 표시합니다.'),
    'msg':('검증 오류 메시지', '입력값 검증기가 반환한 상세 오류입니다. 실제 응답 문구는 검증기 기본 언어일 수 있습니다.'),
    'type':('오류 종류', '입력값 검증 오류를 구분하는 코드입니다.'),
    'input':('검증에 실패한 입력값', '검증 오류가 발생한 원래 입력값입니다.'),
    'ctx':('검증 오류 추가 정보', '허용 범위 등 검증 오류를 설명하는 추가 정보입니다.'),
    'cities':('저장한 여행지 목록', '브라우저에 저장한 여행지를 최대 세 곳 전달합니다. 저장된 비용은 신뢰하지 않고 서버가 다시 계산합니다.'),
    'displayName':('화면에 표시할 이름', '저장 당시 한글 표시 이름입니다. 원래 여행지 식별 이름과 다를 수 있습니다.'),
    'originalName':('원어 이름', '외부 API에서 제공한 원래 도시 이름입니다.'),
    'placeId':('Geoapify 장소 식별자', 'Geoapify 조회 응답의 placeId입니다. 장소 상세 조회에서는 생략하면 좌표를 사용합니다.'),
    'recommendedPlaces':('추천 명소 이름 목록', '저장한 여행지의 명소 이름입니다. 최대 24개이며 각 이름은 200자 이하입니다.'),
    'nameTranslationNotice':('표시 이름 변환 안내', '한글 이름을 확인하지 못했을 때 제공한 안내 문구입니다.'),
    'placeNames':('해당 날짜의 명소 이름', '방문 순서대로 두 곳 또는 세 곳의 서로 다른 명소 이름을 입력합니다. 위치를 확인하지 못하면 경로를 그리지 않습니다.'),
    'mode':('지도 이동 수단', 'walk: 도보, drive: 차량입니다. AI의 이동수단 제안과 별도로 선택하며 대중교통 배차·실시간 교통을 보장하지 않습니다.'),
}

SCHEMA_DOCS = {
    'FlightSearchRequest':('선택 지역 항공권 조회 입력', '선택 지역과 공항·출발일·여행 일수로 왕복 항공권을 조회합니다. 출발일은 필수이며 귀국일은 출발일에 여행 일수에서 1을 뺀 값을 더해 계산합니다. 항공료는 1인 검색가이며 여러 명은 인원수로 곱한 추정입니다.'),
    'MapTranslationRequest':('지도 지명 번역 입력', '현재 화면의 한국어가 없는 지명을 모아 로컬에서 번역합니다.'),
    'BudgetRequest':('여행 예산 입력', '전체 여행 예산을 원 단위 정수로 전달합니다.'),
    'ItineraryRequest':('여행 일정 생성 입력', '선택한 여행지와 여행 조건입니다. 예산은 전체 인원·전체 기간 기준이며 최대 10억원입니다.'),
    'RecommendRequest':('여행 후보 조합 추천 입력', '총예산 1원~1억원 안에서 최대 세 곳의 여행 후보 조합을 비교합니다.'),
    'DisplayNameRequest':('여행지 한글 표시 이름 입력', '기존 여행지 이름과 좌표로 표시 이름을 확인합니다. 여행지 자체는 변경하지 않습니다.'),
    'EstimateRequest':('여행 경비 계산 입력', '선택한 여행지의 교통·숙박·식비 등을 현재 조건으로 계산합니다.'),
    'HTTPValidationError':('요청 입력값 검증 오류', '필수 항목 누락이나 허용 범위를 벗어난 입력 등에 대한 오류 목록입니다.'),
    'ValidationError':('개별 입력값 오류', '오류 위치, 메시지, 종류를 표시합니다.'),
    'ComparisonRequest':('여행지 비교 입력', '조회한 후보 중 예상 비용 상한이 예산 이하인 모든 여행지를 비교합니다.'),
    'SavedDestination':('저장한 여행지 정보', '원래 여행지 이름·좌표와 저장한 표시 정보를 복원합니다.'),
    'RestoreRequest':('저장한 계획 복원 입력', '저장한 여행지를 복원하고 현재 여행 조건으로 경비를 다시 계산합니다.'),
    'NearbyRequest':('주변 명소 조회 입력', '현재 조회하거나 복원한 여행지의 식별 이름을 입력합니다.'),
    'PlaceDetailsRequest':('장소 상세 조회 입력', '장소 식별자 또는 좌표로 운영시간·홈페이지 등 제공 정보를 확인합니다.'),
    'DayRouteRequest':('날짜별 이동 경로 입력', '선택한 도시 주변의 명소 위치를 확인한 후 실제 지도 이동 경로를 조회합니다.'),
}

OPERATIONS = {
    '/api/flights/options':('여행 경비 계산','선택 지역의 출발·도착 공항 확인',
        '로컬 OurAirports 자료에서 대한민국 출발 공항과 선택 지역 국가의 가까운 도착 공항을 제공합니다. 유료 항공권 검색은 실행하지 않습니다. configured는 키 설정 여부이며 실제 인증 성공 여부를 보장하지 않습니다. 공항 거리는 직선거리이고 운항 여부를 뜻하지 않습니다.'),
    '/api/flights/search':('여행 경비 계산','선택 지역의 왕복 항공료 조회와 총경비 재계산',
        '명시적 요청에만 SerpApi Google Flights 검색을 실행합니다. 출국편과 귀국편을 확인하는 최대 2회 요청을 사용하며 전체 후보를 조회하지 않습니다. 1인 이코노미 왕복 원화 검색가를 반환하고 인원수로 곱해 항공료를 교체한 costBreakdown을 제공합니다. 여러 명의 동일 요금·좌석은 검증하지 않습니다. 날짜·조건이 일치하지 않거나 귀국편이 없으면 반영하지 않습니다. 동시 동일 조회는 합치고 성공 결과는 10분 캐시합니다. 외부 요청은 앱의 지속형 월간 상한으로 제한하며 실패·시간 초과는 자동 재시도하지 않습니다.'),
    '/api/destination-photo':('여행지 조회','지역 사진 조회','등록된 cityName의 국내 사진은 행정지역 안의 TourAPI 명소 사진을 우선 사용합니다. 공공누리 제1유형 사진과 명소 이름·출처를 반환합니다. 해외 대표 사진은 UNSPLASH_ACCESS_KEY 설정 시 촬영 위치를 대조한 Unsplash 사진을 우선 사용합니다. 키 미설정·한도·사진 없음에는 Wikimedia Commons를 사용합니다. 국내 대체 사진도 Commons를 사용하며, 한글·현지어 이름과 동명이인 문서도 확인합니다. 확인할 수 없거나 외부 조회에 실패하면 photo는 null입니다. 사진은 별도로 조회하므로 추천·일정 생성은 지연시키지 않습니다.'),
    '/api/map/translate':('명소와 지도 경로','지도 지명 한글 번역',
        '등록 이름 사전만 조회합니다. LibreTranslate와 Gemini 및 기존 자동 번역 캐시는 사용하지 않습니다. translations는 등록된 원문·한글 이름 대응표이며, 미등록 이름은 포함하지 않습니다. available은 조회 기능의 준비 상태이고 외부 번역 서버 상태가 아닙니다.'),
    '/api/countries':('여행 조건','지도 선택용 국가 목록과 경계 조회',
        '국가·지역의 한글명, 영문명, 두 글자 국가 코드와 GeoJSON 경계를 반환합니다. Natural Earth의 공개 경계 데이터를 사용하며 외부 번역 API를 호출하지 않습니다. 각 feature의 properties.bounds는 주요 육지 영역으로 지도 화면을 맞추기 위한 위도·경도 경계입니다. 도서 영역도 지도 클릭에 포함됩니다. 북한과 전역 여행금지 10개국은 국가 선택·추천에서 제외합니다(2026-11-04 외교부 확인 기준). 일부 지역만 금지된 국가는 전역 금지로 처리하지 않습니다. 해외 추천은 Geoapify, 국내 추천은 등록된 행정지역 목록을 사용합니다.'),
    '/api/destinations/compare':('여행지 추천','예산 이하 여행지 전체 비교',
        '예산 이하 후보를 금액대·국내외별로 나눠 최대 24개 지역의 관광명소를 동시 최대 4개씩 확인합니다. 일정 생성과 같은 기준으로 중복을 제거한 명소가 여행 일수 × 2곳 이상 확인된 여행지만 비용 상한이 낮은 순으로 반환하며 미확인·명소 부족 지역은 제외합니다. 명소 확인은 최대 15초이고 그 안에 확인된 후보 범위의 결과입니다. 중복 여행지는 제거하며 외부 제공자가 조회한 후보 범위 안의 결과입니다. countryCode를 지정하면 해당 국가의 후보만 비교하며 이전 조회 결과도 동일 국가인지 검사합니다. 응답은 줄 단위 JSON 스트림입니다. progress 이벤트의 phase는 fetch: 여행지 조회, compare: 경비 비교, sights: 관광명소 확인, names: 이름 확인입니다. result 이벤트의 cities에 결과를 전달합니다. 조회 중 실패하면 error 이벤트의 message와 status로 안내합니다. 스트림이 시작된 뒤에는 HTTP 상태가 200이어도 error 이벤트가 올 수 있습니다. 예산에 맞는 후보가 없으면 404 error 이벤트를 반환합니다.'),
    '/api/destinations/restore':('여행지 조회','저장한 여행 계획의 여행지 복원',
        '브라우저에 저장한 도시 정보를 서버에 다시 등록합니다. 경비는 저장된 금액을 사용하지 않고 현재 조건으로 다시 계산합니다. 서버 재시작 후에도 이후 일정·명소 조회를 사용할 수 있게 합니다. 계정 간 동기화나 서버 영구 저장 기능은 아닙니다.'),
    '/api/nearby-places':('명소와 지도 경로','선택한 여행지의 주변 명소 조회',
        'Geoapify Places API로 여행지 주변 15km 안의 관광 명소를 최대 12개 조회합니다. 공급자의 한국어 표기를 우선하고 없으면 원어를 유지합니다. 원어 이름·주소·좌표·placeId를 보존하며 자동 번역하지 않습니다. namePolicy는 현재 등록 이름 정책, nameSource는 공급자 또는 원어 표시임을 나타냅니다.'),
    '/api/place-details':('명소와 지도 경로','장소 운영시간과 공식 홈페이지 조회',
        'Geoapify Place Details API를 사용합니다. 명소 목록과 같은 등록 이름 우선 정책을 적용하고 원어 이름·주소를 보존합니다. openingHours는 제공된 운영시간 원문, website는 공식 홈페이지이며 정보가 없으면 null입니다. 최신 운영 여부나 예약 가능 여부를 보장하지 않습니다.'),
    '/api/day-route':('명소와 지도 경로','일정의 명소를 실제 이동 경로로 연결',
        '명소 두 곳 또는 세 곳을 도시 주변 50km 안에서 지오코딩하고 Geoapify Routing API로 방문 순서의 경로를 조회합니다. lines는 위도·경도 순서의 지도 선 목록, waypoints는 확인된 명소 좌표, distance는 미터, duration은 이동 시간(초)입니다. 체류 시간은 제외합니다. 명소 위치나 경로를 확인하지 못하면 오류를 반환하고 임의의 직선 경로를 만들지 않습니다. 성공 응답은 최대 10분 재사용합니다.'),
    '/api/health':('서버 상태', '서버와 AI 설정 상태 확인',
        '서버 실행 상태를 확인합니다. status는 서버 상태, aiConfigured는 Gemini 키 설정 여부, demoMode는 샘플 일정 모드 여부입니다. 키 설정 여부가 실제 모델 호출 성공을 보장하지는 않습니다.'),
    '/api/trip-options':('여행 조건', '선택 가능한 출발 지역 조회',
        '출발 지역 목록을 반환합니다. origins의 value는 요청에 넣을 지역 코드, label은 화면에 표시할 한글 지역명입니다.'),
    '/api/cities':('여행지 조회', '기본 여행지 목록 조회',
        '앱에 등록된 기본 도시 목록을 반환합니다. Geoapify의 전체 도시 목록이 아닙니다. 기본 estimatedCost는 저장된 참고값이며 현재 조건으로 계산하려면 여행 경비 계산 API를 사용하세요.'),
    '/api/destinations/search':('여행지 조회', '도시 또는 관광지 검색',
        '국내는 등록 행정지역 목록, 해외는 Geoapify 검색 API를 사용합니다. cities는 검색 결과, message는 결과 안내입니다. 등록 지명 사전을 대조하고 미확인 이름은 원어로 유지합니다. 자동 번역 API는 사용하지 않으며 조회 결과는 서버의 영구 저장소에 보관합니다.'),
    '/api/destinations/random':('여행지 추천', '예산 맞춤 추천 또는 랜덤 여행지 추첨',
        'budget을 생략하면 예산 제한 없이 추첨합니다. countryCode가 없을 때 전체 지역의 랜덤 추첨은 국내·해외를 절반 확률로 먼저 선택합니다. countryCode를 지정하면 해당 국가 안에서만 선택하며 국가와 국내·해외 조건이 다르면 요청을 거절합니다.\n\n'
        'budget을 입력하면 예상 비용 상한이 예산 이하인 후보만 비교합니다. 가장 높은 상한액과의 차이가 예산의 5% 이내인 후보들에서 무작위로 선택합니다. 해외는 Geoapify 도시 후보, 국내는 등록 행정지역 후보를 사용하며 전 세계 모든 여행지를 전수 검색하지는 않습니다. 전체 지역의 예산 추천은 국내·해외를 동시에 조회합니다.\n\n'
        '응답의 city는 선택된 여행지와 costBreakdown 경비 상세입니다. budget은 입력 예산이며, budgetBasis의 upperEstimate는 예상 상한 기준, unrestricted는 예산 제한 없음을 뜻합니다. 경비는 실제 항공권·숙박 판매가가 아닌 추정치입니다. 같은 해외 권역의 API 응답은 5분간 재사용하며 경비는 입력 조건으로 다시 계산합니다. 한글 변환이 늦거나 실패하면 원어 도시명과 안내를 제공합니다.'),
    '/api/destinations/display-name':('여행지 조회', '여행지 한글 표시 이름 확인',
        '여행지의 원래 식별 이름과 좌표를 유지하며 displayName을 반환합니다. 국가·위치에 맞는 등록 지명 사전을 사용하고 미등록 이름은 originalName으로 표시합니다. namePolicy는 registered-v1이며, 한국어 이름이 없으면 nameLocalized=false와 안내를 반환합니다. 자동 번역 API와 이전 번역 캐시는 사용하지 않습니다.'),
    '/api/estimate':('여행 경비', '현재 여행 조건으로 예상 경비 계산',
        '교통·숙박·식비·현지 교통·관광비와 소계의 10% 예비비를 계산합니다. 해외는 보험·통신비도 포함합니다. total은 전체 예상 합계, low와 high는 예상 하한·상한, perPerson은 1인 비용, items는 항목별 금액과 근거, warnings는 참고사항입니다. 실제 예약 가격이나 예약 가능 여부를 조회하지 않습니다.'),
    '/api/recommend':('여행지 추천', '예산 안의 여행 후보 조합 추천',
        '기본 목록 또는 destinationNames로 지정한 후보에서 예상 합계가 예산 이하인 최대 세 곳의 조합을 계산합니다. 후보 개수, 만족도 합계, 낮은 비용 순으로 우선합니다. 기본 화면의 한 곳 추첨과는 별도 기능이며, 여러 도시를 순서대로 방문하는 이동 경로가 아닙니다. cities는 후보 목록, totalCost는 후보 비용 합계, totalSatisfaction은 앱의 참고 만족도 합계입니다. 외부 실제 평점은 아닙니다.'),
    '/api/generate-itinerary':('AI 여행 일정', '선택한 여행지의 여행 일정 생성',
        'Gemini로 하루 오전·오후·저녁의 간결한 동선을 생성합니다. text는 경비 요약과 일정, source는 gemini 또는 demo, cityName은 여행지 식별 이름입니다. demo는 고정 샘플이며 AI 생성 결과가 아닙니다.\n\n'
        '동일 도시·기간·스타일·날짜·명소·모델의 성공 일정은 최대 6시간 재사용하고 동시 요청을 합칩니다. 인원이나 교통·숙박 가격만 바뀌면 동선은 재사용하고 경비 안내를 다시 계산합니다. 실제 예약이나 운영시간 확인은 수행하지 않습니다. 실제 생성에는 유효한 Gemini 키와 접근 가능한 모델이 필요합니다.'),
}

ERRORS = {
    '404':'요청한 여행지가 없거나 조회 후보 중 예산 조건에 맞는 곳이 없습니다.',
    '409':'이전에 조회한 여행지 정보가 만료되었거나 다시 조회해야 합니다.',
    '422':'필수 항목, 입력 형식 또는 허용 범위를 확인해주세요.',
    '429':'외부 API 또는 Gemini 사용 한도에 도달했습니다.',
    '502':'외부 API 응답, 인증, 모델 또는 생성 결과에 문제가 있습니다.',
    '503':'API 키가 없거나 현재 외부 기능을 사용할 수 없습니다.',
    '504':'외부 API 조회 또는 AI 생성 대기 시간이 초과됐습니다.',
}

OPERATION_ERRORS = {
    '/api/flights/options':('404','422'),
    '/api/flights/search':('404','422','429','502','503','504'),
    '/api/destination-photo':('404','422'),
    '/api/map/translate':('422',),
    '/api/countries':('503',),
    '/api/destinations/compare':('422',),
    '/api/destinations/restore':('422','503'),
    '/api/nearby-places':('404','422','429','502','503','504'),
    '/api/place-details':('404','422','429','502','503','504'),
    '/api/day-route':('404','422','429','502','503','504'),
    '/api/health':(), '/api/trip-options':(), '/api/cities':('422',),
    '/api/destinations/search':('422','429','502','503','504'),
    '/api/destinations/random':('404','422','429','502','503','504'),
    '/api/destinations/display-name':('409','422','503'),
    '/api/estimate':('404','422'), '/api/recommend':('409','422'),
    '/api/generate-itinerary':('404','422','429','502','503','504'),
}


def configure_korean_docs(app):
    app.title = '트립버짓 여행 추천 API'
    app.description = (
        '공개 사용량 보호: 요청 횟수·일일 상한 초과 시 429, 동시 처리 초과 시 503과 Retry-After를 반환합니다. 요청 본문은 기본 128KiB로 제한합니다.\n\n'
        '여행지 조회·예산 추천·예상 경비·AI 일정 생성을 확인하는 개발 문서입니다.\n\n'
        '**사용 순서:** 여행지 조회 또는 추첨 → 응답의 cityName 확인 → 경비 계산 또는 일정 생성. '
        '각 항목을 펼쳐 설명을 확인하고 입력값을 넣어 실행할 수 있습니다.\n\n'
        '**입력 안내:** API 주소와 JSON 필드 이름은 영문 식별자를 그대로 사용합니다. '
        '금액은 원 단위 정수, 날짜는 연-월-일 형식입니다. API 키는 서버 설정 파일에만 보관하며 이 화면에 입력하지 않습니다.'
    )
    app.openapi_tags = [{'name':name, 'description':description} for name,description in (
        ('서버 상태','서버 실행 및 AI 설정 상태를 확인합니다.'),
        ('여행 조건','요청에 사용할 출발 지역을 확인합니다.'),
        ('여행지 조회','여행지를 검색하고 표시 이름을 확인합니다.'),
        ('여행지 추천','예산에 맞는 후보 또는 무작위 여행지를 추천합니다.'),
        ('여행 경비','입력한 조건에 따른 계획용 예상 경비를 계산합니다.'),
        ('AI 여행 일정','선택한 여행지의 일정을 생성합니다.'),
        ('명소와 지도 경로','주변 명소와 장소 상세 정보, 날짜별 실제 이동 경로를 확인합니다.'),
    )]

    def korean_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description,
                             openapi_version=app.openapi_version, routes=app.routes, tags=app.openapi_tags)
        for path, methods in schema['paths'].items():
            if path not in OPERATIONS:
                continue
            tag, summary, description = OPERATIONS[path]
            for operation in methods.values():
                operation.update(tags=[tag], summary=summary, description=description)
                for parameter in operation.get('parameters', []):
                    if parameter['name'] in FIELD_DOCS:
                        title, detail = FIELD_DOCS[parameter['name']]
                        parameter['description'] = detail
                        parameter['schema']['title'] = title
                if 'requestBody' in operation:
                    operation['requestBody']['description'] = '아래 형식에 맞춰 요청 내용을 입력합니다. 금액은 원 단위 정수입니다.'
                operation['responses']['200']['description'] = '요청을 정상 처리했습니다. 반환 항목은 위 API 설명을 참고하세요.'
                for status in OPERATION_ERRORS[path]:
                    detail = ERRORS[status]
                    # Preserve FastAPI's validation schema while localizing its explanation.
                    response = operation['responses'].setdefault(status, {})
                    response['description'] = detail
                    if status != '422':
                        response['content'] = {'application/json':{'schema':{'type':'object', 'properties':{
                            'detail':{'type':'string', 'title':'오류 안내', 'description':'처리 실패 이유를 설명합니다.'}}},
                            'example':{'detail':detail}}}
        for name, component in schema.get('components', {}).get('schemas', {}).items():
            if name in SCHEMA_DOCS:
                component['title'], component['description'] = SCHEMA_DOCS[name]
            for field, definition in component.get('properties', {}).items():
                if field in FIELD_DOCS:
                    definition['title'], definition['description'] = FIELD_DOCS[field]
        app.openapi_schema = schema
        return schema

    app.openapi = korean_openapi
