#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using i64 = int64_t;
using u32 = uint32_t;
static constexpr i64 DAY = 86400000LL, WEEK = 7*DAY, GAP = 1800000LL;
static constexpr i64 BAD_TS = INT64_MIN;

static bool byte_less(std::string_view a, std::string_view b) {
    const size_t lim=std::min(a.size(),b.size());
    for(size_t i=0;i<lim;i++){
        unsigned char ac=(unsigned char)a[i],bc=(unsigned char)b[i];
        if(ac!=bc) return ac<bc;
    }
    return a.size()<b.size();
}
struct SvHash { using is_transparent=void; size_t operator()(std::string_view s) const noexcept {return std::hash<std::string_view>{}(s);} };
struct SvEq { using is_transparent=void; bool operator()(std::string_view a,std::string_view b) const noexcept{return a==b;} };
using StrMap = std::unordered_map<std::string,u32,SvHash,SvEq>;
static uint64_t hash_id(std::string_view s) {
    uint64_t v=14695981039346656037ULL;
    for(unsigned char c:s){ v^=c;v*=1099511628211ULL; }
    return v;
}
static bool parse_unsigned(std::string_view s, i64 &out, i64 cap=INT64_MAX) {
    if(s.empty()) return false;
    i64 n=0;
    for(unsigned char c:s){if(c<'0'||c>'9')return false;
        const int d=c-'0';if(n>(cap-d)/10)return false;
        n=n*10+d;
    }
    out=n;return true;
}
static bool ascii2(std::string_view s,size_t pos,int &v) {
    if(pos+1>=s.size()||s[pos]<'0'||s[pos]>'9'||s[pos+1]<'0'||s[pos+1]>'9')return false;
    v=(s[pos]-'0')*10+(s[pos+1]-'0');return true;
}
static bool ascii4(std::string_view s,size_t pos,int &v){
    int a,b;if(!ascii2(s,pos,a)||!ascii2(s,pos+2,b))return false;
    v=a*100+b;return true;
}
static bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}
static int month_days(int y,int m){static constexpr int days[]={0,31,28,31,30,31,30,31,31,30,31,30,31};return days[m]+(m==2&&leap(y));}
static i64 days_from_civil(int y,unsigned m,unsigned d){
    y -= m<=2;const int era=(y>=0?y:y-399)/400;
    const unsigned yoe=(unsigned)(y-era*400);
    const unsigned doy=(153*(m+(m>2?-3:9))+2)/5+d-1;
    const unsigned yoe_days=yoe*365+yoe/4-yoe/100+doy;
    return era*146097+(i64)yoe_days-719468;
}
static void civil_from_days(i64 z,int&y,unsigned&m,unsigned&d){
    z+=719468;const i64 era=(z>=0?z:z-146096)/146097;
    const unsigned doe=(unsigned)(z-era*146097);
    const unsigned yoe=(doe-doe/1460+doe/36524-doe/146096)/365;
    y=(int)yoe+(int)era*400;
    const unsigned doy=doe-(365*yoe+yoe/4-yoe/100);
    const unsigned mp=(5*doy+2)/153;
    d=doy-(153*mp+2)/5+1;
    m=mp+(mp<10?3:-9);y+=(m<=2);
}
static std::string date_from_days(i64 day){
    int y;unsigned m,d;civil_from_days(day,y,m,d);
    char buf[40];std::snprintf(buf,sizeof(buf),"%04d-%02u-%02u",y,m,d);
    return buf;
}
static i64 parse_timestamp(std::string_view s){
    // F3 epoch milliseconds, nonnegative ASCII decimal with leading zeros.
    if(!s.empty()&&s[0]>='0'&&s[0]<='9'&&s.find_first_not_of("0123456789")==std::string_view::npos){
        i64 out;return parse_unsigned(s,out)?out:BAD_TS;
    }
    const bool utc=(s.size()==20&&s[19]=='Z');
    const bool off=(s.size()==25&&(s[19]=='+'||s[19]=='-')&&s[22]==':');
    if(!utc&&!off)return BAD_TS;
    if(s[4]!='-'||s[7]!='-'||s[10]!='T'||s[13]!=':'||s[16]!=':')return BAD_TS;
    int y,mo,d,h,mi,se;
    if(!ascii4(s,0,y)||!ascii2(s,5,mo)||!ascii2(s,8,d)||!ascii2(s,11,h)||!ascii2(s,14,mi)||!ascii2(s,17,se))return BAD_TS;
    if(mo<1||mo>12||d<1||d>month_days(y,mo)||h>23||mi>59||se>59)return BAD_TS;
    i64 ms=days_from_civil(y,(unsigned)mo,(unsigned)d)*DAY+(i64)h*3600000+(i64)mi*60000+(i64)se*1000;
    if(off){int oh,om;if(!ascii2(s,20,oh)||!ascii2(s,23,om)||oh>23||om>59)return BAD_TS;
        i64 shift=(i64)oh*3600000+(i64)om*60000;
        ms+=(s[19]=='+'?-shift:shift);
    }
    return ms;
}
// CSV rules: LF-only rows; optional entire-field double quotes; no embedded commas/quotes/newlines.
static bool parse_csv(std::string const&line, unsigned expect, std::array<std::string_view,8>&out){
    if(line.empty()||expect>8)return false;
    size_t start=0;unsigned i=0;
    while(true){
        if(i>=expect)return false;
        auto end=line.find(',',start);
        if(end==std::string::npos)end=line.size();
        std::string_view x(line.data()+start,end-start);
        if(x.size()>=2&&x.front()=='"'&&x.back()=='"')x=x.substr(1,x.size()-2);
        if(x.find('"')!=std::string_view::npos)return false;
        out[i++]=x;
        if(end==line.size())break;
        start=end+1;
    }
    return i==expect;
}
static std::vector<fs::path> csv_paths(fs::path dir){
    std::vector<fs::path> res;
    if(!fs::exists(dir)||!fs::is_directory(dir))throw std::runtime_error("Input directory missing: "+dir.string());
    for(auto const &x:fs::directory_iterator(dir))if(x.is_regular_file()&&x.path().extension()==".csv")res.push_back(x.path());
    std::sort(res.begin(),res.end());return res;
}
template<class F> static void rows(fs::path file, unsigned cols,F action){
    std::ifstream in(file,std::ios::binary);if(!in)throw std::runtime_error("Cannot open: "+file.string());
    std::string line;line.reserve(300);std::getline(in,line); // header is mandated.
    std::array<std::string_view,8> fields;
    while(std::getline(in,line))if(parse_csv(line,cols,fields))action(fields);
}
struct DSU{
    StrMap dictionary;
    std::vector<std::string> names;
    std::vector<u32> parent,sz,canonical;
    u32 intern(std::string_view name){
        auto p=dictionary.find(name);if(p!=dictionary.end())return p->second;
        if(names.size()==UINT32_MAX)throw std::runtime_error("Too many user IDs");
        u32 id=(u32)names.size(); names.emplace_back(name);dictionary.emplace(names.back(),id);
        parent.push_back(id);sz.push_back(1);canonical.push_back(id);return id;
    }
    u32 root(u32 i){while(i!=parent[i]){parent[i]=parent[parent[i]];i=parent[i];}return i;}
    void unite(u32 a,u32 b){
        a=root(a);b=root(b);if(a==b)return;
        if(sz[a]<sz[b])std::swap(a,b);
        parent[b]=a;sz[a]+=sz[b];
        if(byte_less(names[canonical[b]],names[canonical[a]]))canonical[a]=canonical[b];
    }
    std::string const& representative(u32 r){return names[canonical[root(r)]];}
};
struct Pool {
    std::vector<char> bytes;
    uint64_t add(std::string_view s){uint64_t off=bytes.size();bytes.insert(bytes.end(),s.begin(),s.end());bytes.push_back('\0');return off;}
    const char* ptr(uint64_t off) const {return bytes.data()+off;}
    void release(){std::vector<char>().swap(bytes);}
};
struct EventRecord{
    uint64_t id_off,hash;
    i64 ingest,ts;
    u32 person;
    int32_t price;
    uint16_t category;
    uint8_t kind,valid;
};
struct Event{ i64 ts; u32 person; int32_t price; uint16_t category; uint8_t kind,pad=0;};
struct ClickRecord{uint64_t off,hash;i64 ts;u32 person,campaign;};
struct Click{ i64 ts;uint64_t off;u32 person,campaign;};
struct Session {i64 start; i64 revenue; bool purchased;int day;};
struct Stats{ i64 sessions=0,purchasing=0,revenue=0,assists=0;};
struct Config{
    fs::path data,output,work;
    i64 start=0,end=0;
    int days=0;
};
static std::string manifest_value(std::string const&s,std::string_view key){
    std::string needle="\""+std::string(key)+"\"";
    auto pos=s.find(needle);if(pos==std::string::npos)throw std::runtime_error("Missing key "+std::string(key));
    pos=s.find(':',pos+needle.size());if(pos==std::string::npos)throw std::runtime_error("Bad manifest");
    pos=s.find('"',pos+1);if(pos==std::string::npos)throw std::runtime_error("Bad manifest");
    auto end=s.find('"',pos+1);if(end==std::string::npos)throw std::runtime_error("Bad manifest");
    return s.substr(pos+1,end-pos-1);
}
static Config config(int argc,char**argv){
    if(argc!=4)throw std::runtime_error("Usage: shopping_core /data /output /tmp/work");
    Config c{argv[1],argv[2],argv[3]};
    std::ifstream f(c.data/"manifest.json");if(!f)throw std::runtime_error("Missing manifest.json");
    std::string contents((std::istreambuf_iterator<char>(f)),{});
    c.start=parse_timestamp(manifest_value(contents,"window_start"));
    c.end=parse_timestamp(manifest_value(contents,"window_end"));
    if(c.start==BAD_TS||c.end==BAD_TS||c.end<=c.start)throw std::runtime_error("Invalid window");
    if(c.start%DAY||c.end%DAY)throw std::runtime_error("Expected midnight UTC windows");
    c.days=(int)((c.end-c.start)/DAY);
    if(c.days<=0||c.days>366)throw std::runtime_error("Unsupported manifest window length");
    fs::create_directories(c.output);fs::create_directories(c.work);
    return c;
}
static void say(std::string s){std::cerr<<"[shopping] "<<s<<"\n";}

int main(int argc,char**argv){
  try{
    auto cfg=config(argc,argv);
    auto start_t=std::chrono::steady_clock::now();
    auto elapsed=[&](){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start_t).count();};
    DSU users;
    // 1. Metadata; category strings sorted in unsigned byte-order for exact tie-breaking.
    StrMap productCategory, campaignLookup;
    std::vector<std::string> cats,channels, campaigns;
    StrMap catLookup;
    rows(cfg.data/"products.csv",2,[&](auto const&v){
        u32 cat;auto it=catLookup.find(v[1]);if(it==catLookup.end()){
            cat=(u32)cats.size();cats.emplace_back(v[1]);catLookup.emplace(cats.back(),cat);
        }else cat=it->second;
        productCategory.emplace(std::string(v[0]),cat);
    });
    int unknownCat=(int)cats.size();cats.emplace_back("unknown");
    rows(cfg.data/"campaigns.csv",2,[&](auto const&v){
        u32 cid=(u32)campaigns.size();
        campaigns.emplace_back(v[0]);channels.emplace_back(v[1]);
        campaignLookup.emplace(campaigns.back(),cid);
    });
    const u32 organic=(u32)campaigns.size();
    campaigns.emplace_back("organic");channels.emplace_back("organic");
    // 2. All links before user events/clicks; earliest union establishes person IDs.
    uint64_t links=0;
    for(auto const&path:csv_paths(cfg.data/"links"))rows(path,2,[&](auto const&v){
        if(v[0].empty()||v[1].empty())return;
        users.unite(users.intern(v[0]),users.intern(v[1]));++links;
    });
    say("links="+std::to_string(links)+", known_user_ids="+std::to_string(users.names.size())+", metadata="+std::to_string(elapsed())+"ms");
    // 3. Clicks first; every linked ID already has a global canonical root.
    std::vector<ClickRecord> rawclicks;
    Pool clickIds;
    for(auto const&path:csv_paths(cfg.data/"clicks"))rows(path,4,[&](auto const&v){
        if(v[0].empty()||v[1].empty())return;
        auto it=campaignLookup.find(v[2]);if(it==campaignLookup.end())return;
        i64 t=parse_timestamp(v[3]);if(t==BAD_TS||t<cfg.start-WEEK||t>=cfg.end)return;
        u32 person=users.root(users.intern(v[1]));
        rawclicks.push_back({clickIds.add(v[0]),hash_id(v[0]),t,person,it->second});
    });
    std::sort(rawclicks.begin(),rawclicks.end(),[&](auto const&a,auto const&b){
        if(a.hash!=b.hash)return a.hash<b.hash;
        return std::strcmp(clickIds.ptr(a.off),clickIds.ptr(b.off))<0;
    });
    std::vector<Click> clicks;clicks.reserve(rawclicks.size());
    const char* previous=nullptr;
    for(auto const&c:rawclicks){
        const char*cur=clickIds.ptr(c.off);
        if(previous!=nullptr&&std::strcmp(previous,cur)==0)continue;
        clicks.push_back({c.ts,c.off,c.person,c.campaign});previous=cur;
    }
    std::vector<ClickRecord>().swap(rawclicks);
    std::sort(clicks.begin(),clicks.end(),[&](auto const&a,auto const&b){
        if(a.person!=b.person)return a.person<b.person;
        if(a.ts!=b.ts)return a.ts<b.ts;
        return std::strcmp(clickIds.ptr(a.off),clickIds.ptr(b.off))<0;
    });
    say("valid_unique_clicks="+std::to_string(clicks.size())+", elapsed="+std::to_string(elapsed())+"ms");
    // 4. Parse events BEFORE validation, then deduplicate by ID and earliest ingest.
    std::vector<EventRecord> records;
    Pool eventIds;
    for(auto const&path:csv_paths(cfg.data/"events"))rows(path,7,[&](auto const&v){
        if(v[0].empty())return; // malformed rows already excluded
        i64 ingest=parse_timestamp(v[3]);if(ingest==BAD_TS)return; // guaranteed F1 in official generator
        bool valid=!v[1].empty()&&!v[5].empty();
        i64 t=parse_timestamp(v[2]);
        valid&=t!=BAD_TS&&t>=cfg.start&&t<cfg.end;
        valid&=(v[4]=="view"||v[4]=="cart"||v[4]=="purchase");
        if(valid)valid&=(ingest-t<=DAY);
        int32_t price=0;
        int kind=(v[4]=="purchase")?2:(v[4]=="cart")?1:0;
        if(kind==2){i64 p;bool ok=parse_unsigned(v[6],p,10000000)&&p>=1;
            valid&=ok;if(ok)price=(int32_t)p;
        }
        u32 person=0;uint16_t category=(uint16_t)unknownCat;
        if(valid){person=users.root(users.intern(v[1]));
            auto prod=productCategory.find(v[5]);
            if(prod!=productCategory.end())category=(uint16_t)prod->second;
        }
        records.push_back({eventIds.add(v[0]),hash_id(v[0]),ingest,t,person,price,category,(uint8_t)kind,(uint8_t)valid});
    });
    say("parsed_events="+std::to_string(records.size())+", elapsed="+std::to_string(elapsed())+"ms");
    std::sort(records.begin(),records.end(),[&](auto const&a,auto const&b){
        if(a.hash!=b.hash)return a.hash<b.hash;
        int cmp=std::strcmp(eventIds.ptr(a.id_off),eventIds.ptr(b.id_off));
        if(cmp)return cmp<0;
        return a.ingest<b.ingest;
    });
    // A large raw event vector is released BEFORE loading compact valid events back in memory.
    fs::path compact=cfg.work/"valid_events.bin";
    FILE* out=std::fopen(compact.c_str(),"wb");
    if(!out)throw std::runtime_error("Cannot write compact event scratch file");
    std::setvbuf(out,nullptr,_IOFBF,1<<20);
    uint64_t valid_count=0;const char*prior=nullptr;
    for(auto const&e:records){
        const char*now=eventIds.ptr(e.id_off);
        if(prior&&std::strcmp(prior,now)==0)continue;
        prior=now;
        if(!e.valid)continue; // no later duplicate can rescue invalid first copy
        Event small{e.ts,e.person,e.price,e.category,e.kind,0};
        if(std::fwrite(&small,sizeof(small),1,out)!=1)throw std::runtime_error("Scratch write failed (disk full?)");
        ++valid_count;
    }
    if(std::fclose(out))throw std::runtime_error("Cannot flush compact scratch file");
    std::vector<EventRecord>().swap(records);eventIds.release();
    say("surviving_events="+std::to_string(valid_count)+", elapsed="+std::to_string(elapsed())+"ms");
    std::vector<Event> events;
    if(valid_count>(size_t)(std::numeric_limits<size_t>::max()/sizeof(Event)))throw std::runtime_error("Too many events");
    events.resize((size_t)valid_count);
    FILE* fi=std::fopen(compact.c_str(),"rb");if(!fi)throw std::runtime_error("Cannot read event scratch");
    if(std::fread(events.data(),sizeof(Event),(size_t)valid_count,fi)!=valid_count)throw std::runtime_error("Scratch read failed");
    std::fclose(fi);fs::remove(compact);
    std::sort(events.begin(),events.end(),[](auto const&a,auto const&b){
        return a.person!=b.person?a.person<b.person:a.ts<b.ts;
    });
    say("events sorted by canonical person+time, elapsed="+std::to_string(elapsed())+"ms");
    // 5. Produce user_daily.csv (small relative to raw event input) and dense campaign-day counters.
    fs::path userFile=cfg.work/"user_daily.csv";
    std::ofstream userOut(userFile,std::ios::binary);
    if(!userOut)throw std::runtime_error("Cannot open user summary output");
    userOut<<"user_id,day,sessions,events,revenue_cents,top_category\n";
    const int D=cfg.days;
    std::vector<Stats> campaignStats((size_t)campaigns.size()*D);
    auto bucket=[&](u32 c,int day)->Stats& {return campaignStats[(size_t)c*D+day];};
    auto session_day=[&](i64 t)->int{int d=(int)((t-cfg.start)/DAY);if(d<0||d>=D)throw std::runtime_error("Session outside manifest window");return d;};
    std::vector<u32> seen(campaigns.size(),0);
    u32 generation=0;
    std::vector<Session> sessions;
    uint64_t total_sessions=0,user_rows=0;
    i64 total_revenue=0;
    size_t clickPos=0, evPos=0;
    while(evPos<events.size()){
        u32 person=events[evPos].person;
        size_t endEvent=evPos+1;
        while(endEvent<events.size()&&events[endEvent].person==person)endEvent++;
        while(clickPos<clicks.size()&&clicks[clickPos].person<person)clickPos++;
        size_t clickEnd=clickPos;
        while(clickEnd<clicks.size()&&clicks[clickEnd].person==person)clickEnd++;
        sessions.clear();sessions.reserve(std::min<size_t>(endEvent-evPos,100000));
        int dailyDay=-1;
        i64 dailySessions=0,dailyEvents=0,dailyRevenue=0;
        std::vector<i64> catRevenue(cats.size(),0);
        auto flushDaily=[&](){
            if(dailyDay<0)return;
            int best=-1;
            for(size_t c=0;c<catRevenue.size();c++)if(catRevenue[c]>0&&
                (best<0||catRevenue[c]>catRevenue[best]||
                 (catRevenue[c]==catRevenue[best]&&byte_less(cats[c],cats[best]))))best=(int)c;
            // Generator IDs/categories do not contain embedded commas, quotes, LF or CR.
            userOut<<users.representative(person)<<","<<date_from_days(cfg.start/DAY+dailyDay)<<","<<dailySessions<<","<<dailyEvents<<","<<dailyRevenue<<",";
            if(best>=0)userOut<<cats[best];
            userOut<<"\n";user_rows++;
        };
        i64 previousTime=BAD_TS;
        for(size_t i=evPos;i<endEvent;i++){
            auto const&e=events[i];
            bool newSession=(previousTime==BAD_TS||e.ts-previousTime>GAP);
            if(newSession){
                int day=session_day(e.ts);
                if(dailyDay!=day){flushDaily();
                    dailyDay=day;dailySessions=dailyEvents=dailyRevenue=0;
                    std::fill(catRevenue.begin(),catRevenue.end(),0);
                }
                sessions.push_back({e.ts,0,false,day});dailySessions++;total_sessions++;
            }
            previousTime=e.ts;
            Session& s=sessions.back();dailyEvents++;
            if(e.kind==2){s.purchased=true;s.revenue+=e.price;
                dailyRevenue+=e.price;catRevenue[e.category]+=e.price;total_revenue+=e.price;
            }
        }
        flushDaily();
        // Credit: scan time-sorted clicks. First click at each latest timestamp is the smallest click ID.
        size_t next=clickPos;
        size_t bestIdx=clicks.size();
        i64 lastSeenTS=BAD_TS;
        for(auto const&s:sessions){
            while(next<clickEnd&&clicks[next].ts<=s.start){
                auto const&click=clicks[next];
                if(click.ts!=lastSeenTS){bestIdx=next;lastSeenTS=click.ts;}
                next++;
            }
            u32 credit=(bestIdx<clicks.size()&&s.start-clicks[bestIdx].ts<=WEEK)?clicks[bestIdx].campaign:organic;
            auto& st=bucket(credit,s.day);st.sessions++;st.purchasing+=s.purchased;st.revenue+=s.revenue;
        }
        // Assists: small groups scan bounded clicks; large groups union 7-day campaign intervals.
        const uint64_t cross=(uint64_t)sessions.size()*(clickEnd-clickPos);
        if(cross<=12000){
            for(auto const&s:sessions){
                if(++generation==0){std::fill(seen.begin(),seen.end(),0);generation=1;}
                auto from=std::lower_bound(clicks.begin()+clickPos,clicks.begin()+clickEnd,s.start-WEEK,
                  [](Click const&a,i64 t){return a.ts<t;});
                for(auto it=from;it!=clicks.begin()+clickEnd&&it->ts<=s.start;++it){
                    if(seen[it->campaign]!=generation){seen[it->campaign]=generation;bucket(it->campaign,s.day).assists++;}
                }
            }
        }else{
            std::unordered_map<u32,std::vector<i64>> times;
            times.reserve(std::min<size_t>(campaigns.size(),clickEnd-clickPos));
            for(size_t j=clickPos;j<clickEnd;j++)times[clicks[j].campaign].push_back(clicks[j].ts);
            // The person has at least one session. Determine contiguous session indices per UTC day.
            std::vector<size_t> dayBegin((size_t)D+1,0);
            size_t si=0;
            for(int day=0;day<D;day++){
                dayBegin[day]=si;
                while(si<sessions.size()&&sessions[si].day==day)si++;
            }
            dayBegin[D]=sessions.size();
            for(auto const&entry:times){
                auto const& t=entry.second;
                size_t idx=0;
                while(idx<t.size()){
                    i64 L=t[idx],R=t[idx]+WEEK;
                    ++idx;
                    while(idx<t.size()&&t[idx]<=R){ R=std::max(R,t[idx]+WEEK); ++idx; }
                    auto left=std::lower_bound(sessions.begin(),sessions.end(),L,
                        [](Session const&a,i64 x){return a.start<x;});
                    auto right=std::upper_bound(sessions.begin(),sessions.end(),R,
                        [](i64 x,Session const&a){return x<a.start;});
                    const size_t l=(size_t)(left-sessions.begin()),r=(size_t)(right-sessions.begin());
                    if(l==r)continue;
                    for(int day=sessions[l].day;day<=sessions[r-1].day;day++){
                        size_t a=std::max(l,dayBegin[day]),b=std::min(r,dayBegin[day+1]);
                        if(b>a)bucket(entry.first,day).assists+=(i64)(b-a);
                    }
                }
            }
        }
        evPos=endEvent;clickPos=clickEnd;
    }
    userOut.close();
    fs::path campFile=cfg.work/"campaign_daily.csv";
    std::ofstream campOut(campFile,std::ios::binary);
    if(!campOut)throw std::runtime_error("Cannot create campaign summary");
    campOut<<"campaign_id,channel,day,sessions,purchasing_sessions,revenue_cents,assisted_sessions\n";
    uint64_t camp_rows=0;
    i64 c_session_total=0,c_revenue_total=0,c_assisted_total=0,c_nonorganic_sessions=0;
    for(u32 c=0;c<campaigns.size();c++)for(int day=0;day<D;day++){
        auto const&st=bucket(c,day);
        if(st.sessions==0&&st.assists==0)continue;
        campOut<<campaigns[c]<<","<<channels[c]<<","<<date_from_days(cfg.start/DAY+day)<<","<<st.sessions<<","<<st.purchasing<<","<<st.revenue<<","<<st.assists<<"\n";
        c_session_total+=st.sessions;c_revenue_total+=st.revenue;c_assisted_total+=st.assists;
        if(c!=organic)c_nonorganic_sessions+=st.sessions;
        camp_rows++;
    }
    campOut.close();
    if((uint64_t)c_session_total!=total_sessions)throw std::runtime_error("Invariant failure: session totals mismatch");
    if(c_revenue_total!=total_revenue)throw std::runtime_error("Invariant failure: revenue totals mismatch");
    if(c_assisted_total<c_nonorganic_sessions)throw std::runtime_error("Invariant failure: non-organic credited sessions not covered by assists");
    say("complete sessions="+std::to_string(total_sessions)+", user_daily_rows="+std::to_string(user_rows)+", campaign_daily_rows="+std::to_string(camp_rows)+", elapsed="+std::to_string(elapsed())+"ms");
    std::cout<<"user_summary="<<userFile.string()<<"\ncampaign_summary="<<campFile.string()<<"\n";
    return 0;
  }catch(std::exception const& e){std::cerr<<"FATAL: "<<e.what()<<"\n";return 1;}
}
