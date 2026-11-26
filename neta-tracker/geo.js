// District coordinates & Hindi-to-English canonical mapping for GeoJSON matching
export const HINDI_TO_EN_DISTRICT = {
  'आगरा': 'Agra', 'अलीगढ़': 'Aligarh', 'प्रयागराज': 'Allahabad', 'इलाहाबाद': 'Allahabad',
  'अम्बेडकरनगर': 'Ambedkar Nagar', 'अमेठी': 'Amethi', 'अमरोहा': 'Amroha', 'औरैया': 'Auraiya',
  'अयोध्या': 'Faizabad', 'फैजाबाद': 'Faizabad', 'आजमगढ़': 'Azamgarh', 'बागपत': 'Baghpat',
  'बहराइच': 'Bahraich', 'बलिया': 'Ballia', 'बलरामपुर': 'Balrampur', 'बांदा': 'Banda',
  'बाराबंकी': 'Barabanki', 'बरेली': 'Bareilly', 'बस्ती': 'Basti', 'भदोही': 'Sant Ravidas Nagar',
  'संत रविदास नगर': 'Sant Ravidas Nagar', 'बिजनौर': 'Bijnor', 'बदायूं': 'Budaun',
  'बुलन्दशहर': 'Bulandshahr', 'बुलंदशहर': 'Bulandshahr', 'चंदौली': 'Chandauli',
  'चित्रकूट': 'Chitrakoot', 'देवरिया': 'Deoria', 'एटा': 'Etah', 'इटावा': 'Etawah',
  'फर्रुखाबाद': 'Farrukhabad', 'फतेहपुर': 'Fatehpur', 'फिरोजाबाद': 'Firozabad',
  'गौतमबुद्ध नगर': 'Gautam Buddha Nagar', 'गाजियाबाद': 'Ghaziabad', 'गाजीपुर': 'Ghazipur',
  'गोंडा': 'Gonda', 'गोरखपुर': 'Gorakhpur', 'हमीरपुर': 'Hamirpur', 'हापुड़': 'Hapur',
  'हरदोई': 'Hardoi', 'हाथरस': 'Hathras', 'जालौन': 'Jalaun', 'जौनपुर': 'Jaunpur',
  'झाँसी': 'Jhansi', 'झांसी': 'Jhansi', 'कन्नौज': 'Kannauj', 'कानपुर देहात': 'Kanpur Dehat',
  'कानपुर नगर': 'Kanpur Nagar', 'कासगंज': 'Kasganj', 'कौशाम्बी': 'Kaushambi',
  'खीरी': 'Kheri', 'लखीमपुर खीरी': 'Kheri', 'कुशीनगर': 'Kushinagar', 'ललितपुर': 'Lalitpur',
  'लखनऊ': 'Lucknow', 'महराजगंज': 'Maharajganj', 'महोबा': 'Mahoba', 'मैनपुरी': 'Mainpuri',
  'मथुरा': 'Mathura', 'मऊ': 'Mau', 'मेरठ': 'Meerut', 'मिर्जापुर': 'Mirzapur',
  'मुरादाबाद': 'Moradabad', 'मुजफ्फरनगर': 'Muzaffarnagar', 'पीलीभीत': 'Pilibhit',
  'प्रतापगढ़': 'Pratapgarh', 'रायबरेली': 'Rae Bareli', 'रामपुर': 'Rampur',
  'सहारनपुर': 'Saharanpur', 'सम्भल': 'Sambhal', 'संभल': 'Sambhal',
  'सन्त कबीर नगर': 'Sant Kabir Nagar', 'संत कबीर नगर': 'Sant Kabir Nagar',
  'शाहजहाँपुर': 'Shahjahanpur', 'शाहजहांपुर': 'Shahjahanpur', 'शामली': 'Shamli',
  'श्रावस्ती': 'Shravasti', 'सिद्धार्थनगर': 'Siddharthnagar', 'सीतापुर': 'Sitapur',
  'सोनभद्र': 'Sonbhadra', 'सुल्तानपुर': 'Sultanpur', 'उन्नाव': 'Unnao', 'वाराणसी': 'Varanasi',
};

export function normalizeDistrictKey(name) {
  if (!name) return '';
  const clean = name.trim();
  const mapped = HINDI_TO_EN_DISTRICT[clean] || clean;
  return mapped.toLowerCase().replace(/[^a-z0-9]/g, '');
}
