import re
import os
import json
import time
import requests

class UnitConverter:
    """Convert units and currencies inline."""

    def __init__(self):
        self.cache_file = os.path.expanduser("~/.config/wlaunch/exchange_rates.json")
        self._ensure_config_dir()

        # Unit conversion factors (to base unit)
        self.length_units = {
            'km': 1000, 'kilometer': 1000, 'kilometers': 1000,
            'm': 1, 'meter': 1, 'meters': 1, 'metre': 1, 'metres': 1,
            'cm': 0.01, 'centimeter': 0.01, 'centimeters': 0.01,
            'mm': 0.001, 'millimeter': 0.001, 'millimeters': 0.001,
            'mi': 1609.34, 'mile': 1609.34, 'miles': 1609.34,
            'yd': 0.9144, 'yard': 0.9144, 'yards': 0.9144,
            'ft': 0.3048, 'foot': 0.3048, 'feet': 0.3048,
            'in': 0.0254, 'inch': 0.0254, 'inches': 0.0254,
        }

        self.weight_units = {
            'kg': 1, 'kilogram': 1, 'kilograms': 1,
            'g': 0.001, 'gram': 0.001, 'grams': 0.001,
            'mg': 0.000001, 'milligram': 0.000001, 'milligrams': 0.000001,
            'lb': 0.453592, 'lbs': 0.453592, 'pound': 0.453592, 'pounds': 0.453592,
            'oz': 0.0283495, 'ounce': 0.0283495, 'ounces': 0.0283495,
            'ton': 1000, 'tons': 1000, 'tonne': 1000, 'tonnes': 1000,
        }

        self.volume_units = {
            'l': 1, 'liter': 1, 'liters': 1, 'litre': 1, 'litres': 1,
            'ml': 0.001, 'milliliter': 0.001, 'milliliters': 0.001,
            'gal': 3.78541, 'gallon': 3.78541, 'gallons': 3.78541,
            'qt': 0.946353, 'quart': 0.946353, 'quarts': 0.946353,
            'pt': 0.473176, 'pint': 0.473176, 'pints': 0.473176,
            'cup': 0.236588, 'cups': 0.236588,
        }

        # Temperature needs special handling (not linear)
        self.temp_units = ['celsius', 'fahrenheit', 'kelvin', 'c', 'f', 'k']

        # Common currency codes
        self.currencies = [
            'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'INR', 'CAD', 'AUD',
            'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'RUB', 'BRL', 'MXN',
            'ZAR', 'KRW', 'SGD', 'HKD', 'NZD', 'TRY', 'AED', 'SAR'
        ]

    def _ensure_config_dir(self):
        """Ensure config directory exists."""
        config_dir = os.path.dirname(self.cache_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

    def detect_and_convert(self, text):
        """Detect conversion pattern and perform conversion."""
        # Pattern: <number> <unit> to <unit>
        # Examples: "10 km to miles", "100 USD to EUR", "32 celsius to fahrenheit"
        pattern = r'(\d+\.?\d*)\s*([a-zA-Z]+)\s+to\s+([a-zA-Z]+)'
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            return None

        value = float(match.group(1))
        from_unit = match.group(2).lower()
        to_unit = match.group(3).lower()

        # Try different conversion types
        result = None

        # Try length
        if from_unit in self.length_units and to_unit in self.length_units:
            result = self._convert_units(value, from_unit, to_unit, self.length_units, 'length')

        # Try weight
        elif from_unit in self.weight_units and to_unit in self.weight_units:
            result = self._convert_units(value, from_unit, to_unit, self.weight_units, 'weight')

        # Try volume
        elif from_unit in self.volume_units and to_unit in self.volume_units:
            result = self._convert_units(value, from_unit, to_unit, self.volume_units, 'volume')

        # Try temperature
        elif from_unit in self.temp_units and to_unit in self.temp_units:
            result = self._convert_temperature(value, from_unit, to_unit)

        # Try currency
        elif from_unit.upper() in self.currencies and to_unit.upper() in self.currencies:
            result = self._convert_currency(value, from_unit.upper(), to_unit.upper())

        return result

    def _convert_units(self, value, from_unit, to_unit, unit_dict, unit_type):
        """Convert between units using conversion factors."""
        # Convert to base unit, then to target unit
        base_value = value * unit_dict[from_unit]
        result_value = base_value / unit_dict[to_unit]

        # Format result
        if result_value >= 1000 or result_value < 0.01:
            formatted = f"{result_value:.2e}"
        elif result_value >= 100:
            formatted = f"{result_value:.1f}"
        else:
            formatted = f"{result_value:.4f}".rstrip('0').rstrip('.')

        return {
            'result': f"{value} {from_unit} = {formatted} {to_unit}",
            'value': str(result_value),
            'explanation': f'{unit_type.capitalize()} conversion'
        }

    def _convert_temperature(self, value, from_unit, to_unit):
        """Convert temperature between Celsius, Fahrenheit, and Kelvin."""
        # Normalize unit names
        from_unit = from_unit.lower()
        to_unit = to_unit.lower()

        if from_unit in ['c', 'celsius']:
            celsius = value
        elif from_unit in ['f', 'fahrenheit']:
            celsius = (value - 32) * 5/9
        elif from_unit in ['k', 'kelvin']:
            celsius = value - 273.15
        else:
            return None

        # Convert from celsius to target
        if to_unit in ['c', 'celsius']:
            result = celsius
        elif to_unit in ['f', 'fahrenheit']:
            result = (celsius * 9/5) + 32
        elif to_unit in ['k', 'kelvin']:
            result = celsius + 273.15
        else:
            return None

        formatted = f"{result:.2f}".rstrip('0').rstrip('.')

        return {
            'result': f"{value}° {from_unit.upper()} = {formatted}° {to_unit.upper()}",
            'value': str(result),
            'explanation': 'Temperature conversion'
        }

    def _convert_currency(self, value, from_curr, to_curr):
        """Convert currency using exchange rates."""
        # Load cached rates
        rates = self._load_cached_rates()

        if not rates or self._is_cache_expired(rates):
            # Fetch new rates
            rates = self._fetch_exchange_rates()
            if not rates:
                return {
                    'result': f"Currency conversion unavailable",
                    'value': '0',
                    'explanation': 'Cannot fetch exchange rates (offline or API limit reached)'
                }

        # Perform conversion
        try:
            # Rates are typically base USD, so we need to convert
            if from_curr == 'USD':
                rate = rates.get(to_curr, 1)
                result = value * rate
            elif to_curr == 'USD':
                rate = rates.get(from_curr, 1)
                result = value / rate
            else:
                # Convert via USD
                from_rate = rates.get(from_curr, 1)
                to_rate = rates.get(to_curr, 1)
                result = (value / from_rate) * to_rate

            formatted = f"{result:.2f}"

            return {
                'result': f"{value} {from_curr} = {formatted} {to_curr}",
                'value': str(result),
                'explanation': f'Exchange rate (updated: {rates.get("updated", "unknown")})'
            }
        except Exception as e:
            print(f"Currency conversion error: {e}")
            return {
                'result': f"Currency conversion failed",
                'value': '0',
                'explanation': str(e)
            }

    def _load_cached_rates(self):
        """Load cached exchange rates."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cached rates: {e}")
            return None

    def _save_cached_rates(self, rates):
        """Save exchange rates to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(rates, f, indent=2)
        except Exception as e:
            print(f"Error saving cached rates: {e}")

    def _is_cache_expired(self, rates):
        """Check if cache is older than 24 hours."""
        timestamp = rates.get('timestamp', 0)
        return (time.time() - timestamp) > 86400  # 24 hours

    def _fetch_exchange_rates(self):
        """Fetch exchange rates from API."""
        try:
            # Using exchangerate-api.io free tier
            response = requests.get(
                'https://api.exchangerate-api.com/v4/latest/USD',
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates', {})
                rates['timestamp'] = time.time()
                rates['updated'] = time.strftime('%Y-%m-%d %H:%M')

                # Save to cache
                self._save_cached_rates(rates)

                return rates
            else:
                print(f"API error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print("Exchange rate API timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Exchange rate API error: {e}")
            return None
        except Exception as e:
            print(f"Error fetching rates: {e}")
            return None
