const instruments =  [
    {
      "instrument_token": 256265,
      "name": "NIFTY 50",
      "tradingsymbol": "NIFTY",
      "underlying_instrument": "NIFTY",
      "expiry": "",
      "strike": 0,
      "tick_size": 0,
      "lot_size": 0,
      "multiplier": 1,
      "is_underlying": true,
      "is_non_fno": false,
      "tradable": false,
      "broker": "2",
      "mode": "full",
      "exchange": "NSE",
      "segment": "NSE-INDICES",
      "instrument_type": "EQ",
      "last_price": 18877.7,
      "last_updated_at": "2023-10-26T12:47:59+05:30",
      "last_traded_timestamp": 0,
      "sectors": [
        "Index"
      ]
    }
  ];

const InstrumentLatestPriceCache = new Map( [])

module.exports = {
  instruments: function () {
      return instruments.filter (  i=>!!!i.is_non_fno ).map(i=>{
        return i.instrument_token
      }) ;
  },
  instrument_ids : function(){

  },
  iCache: InstrumentLatestPriceCache,
};
