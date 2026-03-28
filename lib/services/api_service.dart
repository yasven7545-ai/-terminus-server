import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'https://YOUR-RAILWAY-URL.up.railway.app';
  String? token;
  String? activeProperty;
  List<String> properties = [];

  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Future<Map<String, dynamic>> login(
      String username, String password, String property) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/mobile/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'password': password,
        'property': property
      }),
    );
    final data = jsonDecode(res.body);
    if (data['success'] == true) {
      token          = data['token'];
      activeProperty = data['active_property'];
      properties     = List<String>.from(data['properties']);
    }
    return data;
  }

  Future<Map<String, dynamic>> getDashboard() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/mobile/dashboard'),
      headers: _headers,
    );
    return jsonDecode(res.body);
  }

  Future<List<dynamic>> getWorkOrders() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/mobile/workorders'),
      headers: _headers,
    );
    return (jsonDecode(res.body) as Map)['data'] ?? [];
  }

  Future<List<dynamic>> getIssues() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/mobile/issues'),
      headers: _headers,
    );
    return (jsonDecode(res.body) as Map)['data'] ?? [];
  }

  Future<dynamic> getPPM() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/mobile/ppm'),
      headers: _headers,
    );
    return (jsonDecode(res.body) as Map)['data'];
  }
}
