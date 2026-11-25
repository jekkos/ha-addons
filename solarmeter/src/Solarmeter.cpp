#include <iostream>
#include <iomanip>
#include <cstring>
#include <charconv>
#include <chrono>
#include <thread>
#include <stdexcept>
#include <vector>
#include <sstream>
#include "Solarmeter.h"

const std::set<std::string> Solarmeter::ValidKeys {"log_level", "mqtt_broker", "mqtt_password", "mqtt_port", "mqtt_topic", "mqtt_user", "mqtt_tls_cafile", "mqtt_tls_capath", "payment_kwh", "serial_device", "max_read_iterations", "character_read_delay_µs"};

Solarmeter::Solarmeter(void)
{
  Inverter = new ABBAurora();;
  Mqtt = new SolarmeterMqtt();
  Cfg = new SolarmeterConfig();
}

Solarmeter::~Solarmeter(void)
{
  if (Mqtt->GetConnectStatus())
  {
    Mqtt->PublishMessage("offline", Cfg->GetValue("mqtt_topic") + "/status", 1, true);
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  if (Mqtt) { delete Mqtt; }
  if (Inverter) { delete Inverter; }
  if (Cfg) { delete Cfg; };
}

bool Solarmeter::Setup(const std::string &config)
{
  if (!Cfg->Begin(config))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if (!Cfg->ValidateKeys(Solarmeter::ValidKeys))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  this->SetLogLevel();
  Inverter->SetLogLevel(Log);
  Mqtt->SetLogLevel(Log);
  if (Log & static_cast<unsigned char>(LogLevelEnum::CONFIG))
  {
    Cfg->ShowConfig();
  }
  if (!(Cfg->KeyExists("payment_kwh")))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if (!(Cfg->KeyExists("serial_device")))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if (!(Cfg->KeyExists("max_read_iterations") && !Cfg->KeyExists("character_read_delay_µs")))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if (!Inverter->Setup(Cfg->GetValue("serial_device"), B19200, StringTo<int>(Cfg->GetValue("max_read_iterations")), StringTo<int>(Cfg->GetValue("character_read_delay_µs"))))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadCumulatedEnergy(Datagram.TotalEnergy, CumulatedEnergyEnum::LIFETIME_TOTAL))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  std::cout << "Current meter reading: " << Datagram.TotalEnergy << " kWh" << std::endl;
  
  if (!Mqtt->Begin())
  {
    ErrorMessage = Mqtt->GetErrorMessage();
    return false;
  }
  if (!(Cfg->KeyExists("mqtt_topic")))
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if ((Cfg->KeyExists("mqtt_user") && Cfg->KeyExists("mqtt_password")))
  {
    if (!Mqtt->SetUserPassAuth(Cfg->GetValue("mqtt_user"), Cfg->GetValue("mqtt_password")))
    {
      ErrorMessage = Mqtt->GetErrorMessage();
      return false;
    }
  }
  if (Cfg->KeyExists("mqtt_tls_cafile") || Cfg->KeyExists("mqtt_tls_capath"))
  {
    if (!Mqtt->SetTlsConnection(Cfg->GetValue("mqtt_tls_cafile"), Cfg->GetValue("mqtt_tls_capath")))
    {
      ErrorMessage = Mqtt->GetErrorMessage();
      return false;
    }
  }
  if (!(Cfg->KeyExists("mqtt_broker")) || !(Cfg->KeyExists("mqtt_port")) )
  {
    ErrorMessage = Cfg->GetErrorMessage();
    return false;
  }
  if (!Mqtt->SetLastWillTestament("offline", Cfg->GetValue("mqtt_topic") + "/status", 1, true))
  {
    ErrorMessage = Mqtt->GetErrorMessage();
    return false;
  }
  if (!Mqtt->Connect(Cfg->GetValue("mqtt_broker"), StringTo<double>(Cfg->GetValue("mqtt_port")), 60))
  {
    ErrorMessage = Mqtt->GetErrorMessage();
    return false;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(100));
  
  // Publish HA auto-discovery
  if (!PublishAutoDiscovery())
  {
    std::cout << "Warning: " << GetErrorMessage() << std::endl;
  }
  
  return true;
}

bool Solarmeter::Receive(void)
{
  if (!Inverter->ReadState(State))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadPartNumber(Datagram.PartNum))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadSerialNumber(Datagram.SerialNum))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  ABBAurora::FirmwareRelease firmware;
  if (!Inverter->ReadFirmwareRelease(firmware))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  Datagram.Firmware = firmware.Release;
  
  ABBAurora::ManufacturingDate mfg_date;
  if (!Inverter->ReadManufacturingDate(mfg_date))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  Datagram.MfgDate = std::string("Year ") + mfg_date.Year + " Week " + mfg_date.Week;

  ABBAurora::Version version;
  if (!Inverter->ReadVersion(version))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  Datagram.InverterType = version.Par1;
  Datagram.GridStandard = version.Par2;

  if (!Inverter->ReadCumulatedEnergy(Datagram.TotalEnergy, CumulatedEnergyEnum::LIFETIME_TOTAL))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.VoltageP1, DspValueEnum::V_IN_1))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.CurrentP1, DspValueEnum::I_IN_1))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.PowerP1, DspValueEnum::POWER_IN_1))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.VoltageP2, DspValueEnum::V_IN_2))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.CurrentP2, DspValueEnum::I_IN_2))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.PowerP2, DspValueEnum::POWER_IN_2))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.GridVoltage, DspValueEnum::GRID_VOLTAGE))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.GridCurrent, DspValueEnum::GRID_CURRENT))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.GridPower, DspValueEnum::GRID_POWER))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.Frequency, DspValueEnum::FREQUENCY))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.InverterTemp, DspValueEnum::TEMPERATURE_INVERTER))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.BoosterTemp, DspValueEnum::TEMPERATURE_BOOSTER))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  if (!Inverter->ReadDspValue(Datagram.RIso, DspValueEnum::ISOLATION_RESISTANCE))
  {
    ErrorMessage = Inverter->GetErrorMessage();
    return false;
  }
  try
  {
    float denominator = Datagram.PowerP1 + Datagram.PowerP2;
    if (denominator == 0)
    {
      throw std::runtime_error("Math error: Attempted to divide by Zero");
    } 
    Datagram.Efficiency = Datagram.GridPower / denominator * 100.0f;
  }
  catch (std::runtime_error& e)
  {
    ErrorMessage = e.what();
    return false;
  }
  return true;
}

bool Solarmeter::Publish(void)
{
  unsigned long long now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now().time_since_epoch()).count();
  
  std::ios::fmtflags old_settings = Payload.flags();
  Payload.str(std::string());
  Payload.setf(std::ios::fixed, std::ios::floatfield);

  Payload << "[{"
    << "\"time\":" << now << ","
    << "\"total_energy\":" << std::setprecision(2) << Datagram.TotalEnergy << "," 
    << "\"voltage_p1\":" << std::setprecision(2) << Datagram.VoltageP1 << ","
    << "\"current_p1\":" << std::setprecision(5) << Datagram.CurrentP1 << ","
    << "\"power_p1\":" << std::setprecision(2) << Datagram.PowerP1 << ","
    << "\"voltage_p2\":" << std::setprecision(2) << Datagram.VoltageP2 << ","
    << "\"current_p2\":" << std::setprecision(5) << Datagram.CurrentP2 << ","
    << "\"power_p2\":" << std::setprecision(2) << Datagram.PowerP2 << ","
    << "\"grid_voltage\":" << std::setprecision(2) << Datagram.GridVoltage << ","
    << "\"grid_current\":" << std::setprecision(5) << Datagram.GridCurrent << ","
    << "\"grid_power\":" << std::setprecision(2) << Datagram.GridPower << ","
    << "\"frequency\":" << std::setprecision(3) << Datagram.Frequency << ","
    << "\"efficiency\":" << std::setprecision(2) << Datagram.Efficiency << ","
    << "\"inverter_temp\":" << std::setprecision(2) << Datagram.InverterTemp << ","
    << "\"booster_temp\":" << std::setprecision(2) << Datagram.BoosterTemp << ","
    << "\"r_iso\":" << std::setprecision(3) << Datagram.RIso << ","
    << "\"payment\":" << Cfg->GetValue("payment_kwh")
    << "},{"
    << "\"serial_num\":\"" << Datagram.SerialNum << "\","
    << "\"part_num\":\"" << Datagram.PartNum << "\","
    << "\"mfg_date\":\"" << Datagram.MfgDate << "\","
    << "\"firmware\":\"" << Datagram.Firmware << "\","
    << "\"inverter_type\":\"" << Datagram.InverterType << "\"," 
    << "\"grid_standard\":\"" << Datagram.GridStandard << "\""
    << "}]";

  std::ostringstream oss;
  oss << "[{"
    << "\"global_state\":\"" << State.GlobalState << "\"" << ","
    << "\"inverter_state\":\"" << State.InverterState << "\"" << ","
    << "\"ch1_state\":\"" << State.Channel1State << "\"" << ","
    << "\"ch2_state\":\"" << State.Channel2State << "\"" << ","
    << "\"alarm_state\":\"" << State.AlarmState << "\"" << "}]";

  if (Mqtt->GetNotifyOnlineFlag())
  {
    std::cout << "Solarmeter is online." << std::endl;
    if (!Mqtt->PublishMessage("online", Cfg->GetValue("mqtt_topic") + "/status", 1, true))
    {
      ErrorMessage = Mqtt->GetErrorMessage();
      return false;
    }
  }

  // Publish individual sensor topics for HA auto-discovery
  if (!PublishIndividualSensors())
  {
    return false;
  }

  static ABBAurora::State previous_state;
  if ( Mqtt->GetNotifyOnlineFlag() || 
       (!((previous_state.GlobalState == State.GlobalState) &&
       (previous_state.InverterState == State.InverterState) &&
       (previous_state.Channel1State == State.Channel1State) &&
       (previous_state.Channel2State == State.Channel2State) &&
       (previous_state.AlarmState == State.AlarmState))) )
  {
    if (!(Mqtt->PublishMessage(oss.str(), Cfg->GetValue("mqtt_topic") + "/state", 0, false)))
    {
      ErrorMessage = Mqtt->GetErrorMessage();
      return false;
    }
    previous_state = State;
  }
  if (Mqtt->GetConnectStatus())
  {
    if (!(Mqtt->PublishMessage(Payload.str(), Cfg->GetValue("mqtt_topic") + "/live", 0, false)))
    {
      ErrorMessage = Mqtt->GetErrorMessage();
      return false;
    }
  }
  Mqtt->SetNotifyOnlineFlag(false);

  if (Log & static_cast<unsigned char>(LogLevelEnum::JSON))
  {
    std::cout << Payload.str() << std::endl;
    std::cout << oss.str() << std::endl;
  }
  Payload.flags(old_settings);
  
  return true;
}

std::string Solarmeter::GetErrorMessage(void) const
{
  return ErrorMessage;
}

bool Solarmeter::PublishAutoDiscovery(void)
{
  std::string base = Cfg->GetValue("mqtt_topic");
  std::string unique_base = "solarmeter";
  
  struct SensorDef {
    const char* name;
    const char* unique_id;
    const char* state_topic;
    const char* unit;
    const char* device_class;
    const char* state_class;
  };
  
  SensorDef sensors[] = {
    {"Total Energy",     "total_energy",   "total_energy",   "kWh", "", "total_increasing"},
    {"Power P1",         "power_p1",       "power_p1",       "W",   "apparent_power", ""},
    {"Power P2",         "power_p2",       "power_p2",       "W",   "apparent_power", ""},
    {"Grid Power",       "grid_power",     "grid_power",     "W",   "active_power",   ""},
    {"Voltage P1",       "voltage_p1",     "voltage_p1",     "V",   "voltage",        ""},
    {"Voltage P2",       "voltage_p2",     "voltage_p2",     "V",   "voltage",        ""},
    {"Grid Voltage",     "grid_voltage",   "grid_voltage",   "V",   "voltage",        ""},
    {"Current P1",       "current_p1",     "current_p1",     "A",   "current",        ""},
    {"Current P2",       "current_p2",     "current_p2",     "A",   "current",        ""},
    {"Grid Current",     "grid_current",   "grid_current",   "A",   "current",        ""},
    {"Frequency",        "frequency",      "frequency",      "Hz",  "frequency",      ""},
    {"Efficiency",       "efficiency",     "efficiency",     "%",   "",               ""},
    {"Inverter Temp",    "inverter_temp",  "inverter_temp",  "\u00B0C", "temperature",""},
    {"Booster Temp",     "booster_temp",   "booster_temp",   "\u00B0C", "temperature",""},
    {"Isolation Res",    "r_iso",          "r_iso",          "M\u03A9", "",           ""},
  };
  
  int count = sizeof(sensors) / sizeof(sensors[0]);
  
  for (int i = 0; i < count; i++)
  {
    std::string unique_id = unique_base + "_" + sensors[i].unique_id;
    std::string disc_topic = "homeassistant/sensor/" + unique_id + "/config";
    
    std::ostringstream json;
    json << "{"
      << "\"name\":\"" << sensors[i].name << "\","
      << "\"unique_id\":\"" << unique_id << "\","
      << "\"object_id\":\"" << unique_id << "\","
      << "\"state_topic\":\"" << base << "/" << sensors[i].state_topic << "\","
      << "\"unit_of_measurement\":\"" << sensors[i].unit << "\",";
    
    if (std::string(sensors[i].device_class) != "")
      json << "\"device_class\":\"" << sensors[i].device_class << "\",";
    
    if (std::string(sensors[i].state_class) != "")
      json << "\"state_class\":\"" << sensors[i].state_class << "\",";
    
    json << "\"device\":"
      << "{"
      << "\"identifiers\":[\"" << unique_base << "\"],"
      << "\"name\":\"ABB Aurora Inverter\","
      << "\"model\":\"ABB Aurora\","
      << "\"manufacturer\":\"ABB\""
      << "}"
      << "}";
    
    if (!Mqtt->PublishMessage(json.str(), disc_topic, 1, true))
    {
      ErrorMessage = "Auto-discovery failed: " + Mqtt->GetErrorMessage();
      return false;
    }
    
    std::cout << "Published discovery: " << sensors[i].name << std::endl;
  }
  
  std::cout << "Auto-discovery published for " << count << " sensors" << std::endl;
  return true;
}

bool Solarmeter::PublishIndividualSensors(void)
{
  std::string base = Cfg->GetValue("mqtt_topic");
  
  struct SensorVal {
    const char* topic;
    float value;
  };
  
  SensorVal vals[] = {
    {"total_energy",  Datagram.TotalEnergy},
    {"power_p1",      Datagram.PowerP1},
    {"power_p2",      Datagram.PowerP2},
    {"grid_power",    Datagram.GridPower},
    {"voltage_p1",    Datagram.VoltageP1},
    {"voltage_p2",    Datagram.VoltageP2},
    {"grid_voltage",  Datagram.GridVoltage},
    {"current_p1",    Datagram.CurrentP1},
    {"current_p2",    Datagram.CurrentP2},
    {"grid_current",  Datagram.GridCurrent},
    {"frequency",     Datagram.Frequency},
    {"efficiency",    Datagram.Efficiency},
    {"inverter_temp", Datagram.InverterTemp},
    {"booster_temp",  Datagram.BoosterTemp},
    {"r_iso",         Datagram.RIso},
  };
  
  int count = sizeof(vals) / sizeof(vals[0]);
  
  for (int i = 0; i < count; i++)
  {
    std::ostringstream val_str;
    val_str << std::fixed << std::setprecision(2) << vals[i].value;
    
    if (!Mqtt->PublishMessage(val_str.str(), base + "/" + vals[i].topic, 0, false))
    {
      ErrorMessage = "Sensor publish failed: " + Mqtt->GetErrorMessage();
      return false;
    }
  }
  
  return true;
}

void Solarmeter::SetLogLevel(void)
{
  if (Cfg->KeyExists("log_level"))
  {
    std::string line = Cfg->GetValue("log_level");
    std::istringstream iss(line);
    std::string token;
    std::vector<std::string> log_level;

    while(std::getline(iss, token, ','))
    {
      log_level.push_back(token);
    }
    for (auto it = log_level.cbegin(); it != log_level.cend(); ++it)
    {
      if (!(*it).compare("config"))
      {
        Log |= static_cast<unsigned char>(LogLevelEnum::CONFIG);
      }
      else if (!(*it).compare("json"))
      {
        Log |= static_cast<unsigned char>(LogLevelEnum::JSON);
      }
      else if (!(*it).compare("mosquitto"))
      {
        Log |= static_cast<unsigned char>(LogLevelEnum::MQTT);
      }
      else if (!(*it).compare("serial"))
      {
        Log |= static_cast<unsigned char>(LogLevelEnum::SERIAL);
      }
    }
  }
  else
  {
    Log = 0;
  }
}

unsigned char Solarmeter::GetLogLevel(void) const
{
  return Log;
}

template <typename T>
T Solarmeter::StringTo(const std::string &str) const
{
  T value;
  std::istringstream iss(str);
  iss >> value;
  if (iss.fail())
  {
    return T();
  }
  return value;
}
